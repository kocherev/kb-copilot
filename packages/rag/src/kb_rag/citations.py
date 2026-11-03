"""Which retrieved passages a spoken answer rests on.

Only the answer is embedded. Each passage is compared by the vector the index
already stores for it.
"""

import asyncio
import re
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient

from kb_rag.models import DEFAULT_SETTINGS, RetrievalSettings
from kb_rag.pipeline import DENSE, KB_COLLECTION, cosine, validate_product_id

# Cosine between one answer sentence and a whole stored passage, which holds
# up to 120 words, so the scores run lower than sentence against sentence.
# A passage is cited when a sentence is very close to it, or when a sentence is
# fairly close and nearly every content word of it appears in the passage.
# Measured with the default embedder on the 117 demo eval questions that name
# a source, against each question's top five passages. Gold answers: 0.91
# passages cited per answer, 92.5% from a page the dataset expects, 66% of the
# expected sections cited. Gemini's answers: 82.5% and 45%. The numbers and
# the method are in docs/decisions/0006-lean-runtime.md. A missing citation is
# cheaper than a wrong one, so the cutoffs favor precision.
CLOSE = 0.85
RELATED = 0.55
COVERED = 0.9
# Shorter sentences ("Sure.", "Let me check.") match anything.
MIN_WORDS = 4
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[a-z0-9]+")
# A spoken answer adds "your", "from", "when" where the page has none. In a
# six-word sentence one of them drops coverage under COVERED, so they do not
# count. Negations stay: they change the claim.
_FILLER = frozenset(
    "about after also been before both could does each from have into just more "
    "most other over some such than that their them then there these they this "
    "those very were what when where which while will with would your".split()
)


def sentences(text: str) -> list[str]:
    parts = (part.strip() for part in _SENTENCE_END.split(text))
    return [part for part in parts if len(part.split()) >= MIN_WORDS]


def _content_words(text: str) -> list[str]:
    """Words that carry the claim, with a plural "s" dropped ("requests")."""
    return [
        w.removesuffix("s") if len(w) > 4 else w
        for w in _WORD.findall(text.lower())
        if (len(w) > 3 or w.isdigit()) and w not in _FILLER
    ]


def _covered(sentence: str, passage_words: set[str]) -> float:
    words = _content_words(sentence)
    return sum(w in passage_words for w in words) / len(words) if words else 0.0


async def supported_ids(
    client: AsyncQdrantClient,
    product_id: str,
    answer: str,
    passage_ids: Sequence[str],
    *,
    settings: RetrievalSettings = DEFAULT_SETTINGS,
) -> list[str]:
    """The given passage ids that a sentence of the answer restates, in order."""
    product = validate_product_id(product_id)
    spoken = sentences(answer)
    if not spoken or not passage_ids:
        return []
    points, vectors = await asyncio.gather(
        client.retrieve(
            KB_COLLECTION,
            ids=list(passage_ids),
            with_payload=True,
            with_vectors=[DENSE],
        ),
        asyncio.to_thread(settings.dense.passages, spoken),
    )
    stored = {str(point.id): point for point in points}
    found: list[str] = []
    for passage_id in passage_ids:
        point = stored.get(passage_id)
        payload = point.payload if point else None
        if point is None or not payload or payload.get("product_id") != product:
            continue
        words = set(_content_words(str(payload.get("text", ""))))
        for sentence, spoken_vector in zip(spoken, vectors, strict=True):
            similarity = cosine(spoken_vector, point.vector)
            if similarity >= CLOSE or (
                similarity >= RELATED and _covered(sentence, words) >= COVERED
            ):
                found.append(passage_id)
                break
    return found
