import re
from collections.abc import Sequence

from kb_rag import Passage
from kb_rag.models import DenseEmbedder

from kb_agent.protocol import SNIPPET_LIMIT, CitedPassage

# Cosine similarity between one answer sentence and one passage sentence.
# Measured with the default embedder on the demo eval answers against their top
# five passages: at 0.8, 88% of the cited passages came from a page the dataset
# expects, and 37% of the expected passages were cited. A missing citation is
# cheaper than a wrong one, so the cutoff favors precision.
SUPPORT_THRESHOLD = 0.8
# Shorter sentences ("Sure.", "Let me check.") match anything.
MIN_WORDS = 4
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def sentences(text: str) -> list[str]:
    parts = (part.strip() for part in _SENTENCE_END.split(text))
    return [part for part in parts if len(part.split()) >= MIN_WORDS]


def supporting_passages(
    answer: str,
    passages: Sequence[Passage],
    dense: DenseEmbedder,
    threshold: float = SUPPORT_THRESHOLD,
) -> list[Passage]:
    """Passages with a sentence close in meaning to a sentence of the answer.

    Blocking: it runs the embedder, so call it from a thread.
    """
    spoken = sentences(answer)
    pieces = [(p, s) for p in passages for s in sentences(p.text)]
    if not spoken or not pieces:
        return []
    vectors = dense.passages(spoken + [piece for _, piece in pieces])
    answer_vectors, piece_vectors = vectors[: len(spoken)], vectors[len(spoken) :]
    found: dict[str, Passage] = {}
    for (passage, _), piece in zip(pieces, piece_vectors, strict=True):
        if passage.id not in found and any(
            _dot(piece, heard) >= threshold for heard in answer_vectors
        ):
            found[passage.id] = passage
    return list(found.values())


def cited(passage: Passage) -> CitedPassage:
    return CitedPassage(
        id=passage.id,
        title=passage.title,
        source=passage.source,
        anchor=passage.anchor,
        snippet=" ".join(passage.text.split())[:SNIPPET_LIMIT],
    )


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    # The embedders return unit vectors.
    return sum(x * y for x, y in zip(a, b, strict=True))
