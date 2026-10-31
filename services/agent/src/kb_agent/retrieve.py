import time
from dataclasses import dataclass

from kb_rag.embed import tokens
from kb_rag.pipeline import search_chunks
from qdrant_client import QdrantClient

NOT_IN_DOCS = "That is not in the docs."

# shortcut: evidence is shared words, not a model score. Revisit with real embeddings.
_SKIP = {
    "about",
    "all",
    "and",
    "any",
    "are",
    "but",
    "bye",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "goodbye",
    "had",
    "has",
    "have",
    "hello",
    "help",
    "here",
    "hey",
    "how",
    "into",
    "its",
    "just",
    "know",
    "like",
    "need",
    "not",
    "okay",
    "our",
    "ours",
    "over",
    "please",
    "should",
    "tell",
    "thank",
    "thanks",
    "that",
    "the",
    "them",
    "then",
    "there",
    "they",
    "this",
    "under",
    "want",
    "was",
    "were",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}


@dataclass(frozen=True)
class KbHit:
    source_url: str
    text: str


@dataclass(frozen=True)
class KbSearch:
    hits: tuple[KbHit, ...]
    duration_ms: int

    def source_urls(self) -> list[str]:
        found: list[str] = []
        for hit in self.hits:
            if hit.source_url not in found:
                found.append(hit.source_url)
        return found


def content_tokens(text: str) -> list[str]:
    return [
        token
        for token in tokens(text)
        if token != "empty" and token not in _SKIP and len(token) >= 3
    ]


def search_kb(
    client: QdrantClient,
    product_id: str,
    query: str,
    limit: int = 5,
) -> KbSearch:
    started = time.perf_counter()
    hits: list[KbHit] = []
    if content_tokens(query):
        for row in search_chunks(client, product_id, query, limit=limit):
            source = row["source_url"]
            passage = row["text"]
            if source and _is_evidence(query, passage):
                hits.append(KbHit(source_url=source, text=passage))
    duration_ms = round((time.perf_counter() - started) * 1000)
    return KbSearch(hits=tuple(hits), duration_ms=duration_ms)


def tool_text(found: KbSearch) -> str:
    if not found.hits:
        return f"not in the docs. Say exactly: {NOT_IN_DOCS} Do not invent an answer."
    passages = [
        f"[{index}] source: {hit.source_url}\n{hit.text}"
        for index, hit in enumerate(found.hits, start=1)
    ]
    return (
        "Use only these passages. Do not add facts that are not written here.\n"
        + "\n\n".join(passages)
    )


def citation_suffix(sources: list[str]) -> str:
    return "".join(f"\nSource: {source}" for source in sources)


def retrieval_record(product_id: str, found: KbSearch) -> dict[str, object]:
    return {
        "kind": "retrieval",
        "product_id": product_id,
        "duration_ms": found.duration_ms,
        "hit_count": len(found.hits),
    }


def _is_evidence(query: str, passage: str) -> bool:
    wanted = content_tokens(query)
    if not wanted:
        return False
    have = set(tokens(passage))
    return any(_matches(token, have) for token in wanted)


def _matches(token: str, have: set[str]) -> bool:
    if len(token) < 3:
        return False
    if token in have:
        return True
    if len(token) < 4:
        return False
    return any(
        len(other) >= 4 and (other.startswith(token) or token.startswith(other))
        for other in have
    )
