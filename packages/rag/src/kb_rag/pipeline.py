import asyncio
import math
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    HasIdCondition,
    KeywordIndexParams,
    KeywordIndexType,
    MatchValue,
    Modifier,
    PointStruct,
    Prefetch,
    SparseVectorParams,
    VectorParams,
)

from kb_rag.chunk import chunk_text
from kb_rag.models import DEFAULT_SETTINGS, RetrievalSettings
from kb_rag.sources import Source

NOT_IN_DOCS = "That is not in the docs."
# One shared collection. product_id is a tenant payload index, not a collection.
KB_COLLECTION = "kb_chunks"
DENSE = "dense"
SPARSE = "sparse"


@dataclass(frozen=True)
class Passage:
    id: str
    product_id: str
    source: str
    title: str
    anchor: str
    text: str
    score: float


@dataclass(frozen=True)
class SearchResult:
    passages: tuple[Passage, ...]
    abstained: bool
    timings_ms: dict[str, float]


def validate_product_id(product_id: str) -> str:
    cleaned = product_id.strip()
    if not cleaned:
        raise ValueError("product_id is required")
    if any(character.isspace() or character == "/" for character in cleaned):
        raise ValueError("product_id cannot contain whitespace or slashes")
    return cleaned


def validate_source(source: str) -> str:
    cleaned = source.strip()
    if cleaned.startswith("upload://") and "/" not in cleaned.removeprefix("upload://"):
        return cleaned
    path = PurePosixPath(cleaned)
    if (
        not cleaned
        or ":" in cleaned
        or "\\" in cleaned
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise ValueError(f"source must be a relative path or upload://name: {source}")
    return cleaned


def should_abstain(passages: tuple[Passage, ...], threshold: float | None) -> bool:
    if not passages:
        return True
    return threshold is not None and max(p.score for p in passages) < threshold


async def ensure_collection(
    client: AsyncQdrantClient, settings: RetrievalSettings = DEFAULT_SETTINGS
) -> None:
    if await client.collection_exists(KB_COLLECTION):
        return
    await client.create_collection(
        collection_name=KB_COLLECTION,
        vectors_config={
            DENSE: VectorParams(
                size=settings.dense.size(),
                distance=Distance.COSINE,
            )
        },
        sparse_vectors_config={SPARSE: SparseVectorParams(modifier=Modifier.IDF)},
    )
    await client.create_payload_index(
        collection_name=KB_COLLECTION,
        field_name="product_id",
        field_schema=KeywordIndexParams(type=KeywordIndexType.KEYWORD, is_tenant=True),
    )
    await client.create_payload_index(
        collection_name=KB_COLLECTION,
        field_name="source",
        field_schema=KeywordIndexParams(type=KeywordIndexType.KEYWORD),
    )


async def index_sources(
    client: AsyncQdrantClient,
    product_id: str,
    sources: list[Source],
    *,
    settings: RetrievalSettings = DEFAULT_SETTINGS,
) -> int:
    product = validate_product_id(product_id)
    await ensure_collection(client, settings)
    count = 0
    for source in sources:
        count += await _index_source(client, product, source, settings)
    return count


async def delete_source(
    client: AsyncQdrantClient, product_id: str, source: str
) -> None:
    await client.delete(
        collection_name=KB_COLLECTION,
        points_selector=_source_filter(validate_product_id(product_id), source),
    )


async def search(
    client: AsyncQdrantClient,
    product_id: str,
    query: str,
    *,
    limit: int = 5,
    settings: RetrievalSettings = DEFAULT_SETTINGS,
) -> SearchResult:
    product = validate_product_id(product_id)
    started = time.perf_counter()
    text = query.strip()
    if not text:
        return SearchResult(passages=(), abstained=True, timings_ms={"total": 0.0})
    dense, sparse = await asyncio.gather(
        asyncio.to_thread(settings.dense.query, text),
        asyncio.to_thread(settings.sparse.query, text),
    )
    embedded = time.perf_counter()
    product_filter = Filter(
        must=[FieldCondition(key="product_id", match=MatchValue(value=product))]
    )
    fused = await client.query_points(
        collection_name=KB_COLLECTION,
        prefetch=[
            Prefetch(
                query=dense,
                using=DENSE,
                limit=settings.candidates,
                filter=product_filter,
            ),
            Prefetch(
                query=sparse,
                using=SPARSE,
                limit=settings.candidates,
                filter=product_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=settings.candidates if settings.reranker else limit,
        with_payload=True,
        with_vectors=[DENSE],
    )
    queried = time.perf_counter()
    candidates = [
        _passage(point.id, point.payload or {}, _cosine(dense, point.vector))
        for point in fused.points
    ]
    if settings.reranker and candidates:
        scores = await asyncio.to_thread(
            settings.reranker.scores,
            text,
            [_rerank_text(passage) for passage in candidates],
        )
        candidates = sorted(
            (
                replace(passage, score=score)
                for passage, score in zip(candidates, scores, strict=True)
            ),
            key=lambda passage: passage.score,
            reverse=True,
        )
    reranked = time.perf_counter()
    passages = tuple(candidates[:limit])
    abstained = should_abstain(passages, settings.abstain_threshold)
    return SearchResult(
        passages=() if abstained else passages,
        abstained=abstained,
        timings_ms={
            "embed": _ms(started, embedded),
            "query": _ms(embedded, queried),
            "rerank": _ms(queried, reranked),
            "total": _ms(started, reranked),
        },
    )


async def _index_source(
    client: AsyncQdrantClient,
    product: str,
    source: Source,
    settings: RetrievalSettings,
) -> int:
    name = validate_source(source.source)
    chunks = chunk_text(source.text, markdown=source.markdown, title=_page_title(name))
    if not chunks:
        raise ValueError(f"{name} produced no chunks")
    texts = [f"{chunk.title}\n{chunk.text}" for chunk in chunks]
    dense, sparse = await asyncio.gather(
        asyncio.to_thread(settings.dense.passages, texts),
        asyncio.to_thread(settings.sparse.passages, texts),
    )
    ids = [
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"{product}|{name}|{index}"))
        for index in range(len(chunks))
    ]
    await client.upsert(
        collection_name=KB_COLLECTION,
        points=[
            PointStruct(
                id=point_id,
                vector={DENSE: dense_vector, SPARSE: sparse_vector},
                payload={
                    "product_id": product,
                    "source": name,
                    "title": chunk.title,
                    "anchor": chunk.anchor,
                    "text": chunk.text,
                },
            )
            for point_id, chunk, dense_vector, sparse_vector in zip(
                ids, chunks, dense, sparse, strict=True
            )
        ],
    )
    # Upsert first, then drop chunks the new version no longer has, so a
    # re-index never leaves the source missing from search.
    stale = Filter(
        must=_source_filter(product, name).must,
        must_not=[HasIdCondition(has_id=list(ids))],
    )
    await client.delete(collection_name=KB_COLLECTION, points_selector=stale)
    return len(chunks)


def _source_filter(product: str, source: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="product_id", match=MatchValue(value=product)),
            FieldCondition(key="source", match=MatchValue(value=source)),
        ]
    )


def _page_title(source: str) -> str:
    return Path(source.removeprefix("upload://")).stem.replace("-", " ").capitalize()


def _passage(point_id: object, payload: dict[str, object], score: float) -> Passage:
    return Passage(
        id=str(point_id),
        product_id=str(payload.get("product_id", "")),
        source=str(payload.get("source", "")),
        title=str(payload.get("title", "")),
        anchor=str(payload.get("anchor", "")),
        text=str(payload.get("text", "")),
        score=score,
    )


def _cosine(query: list[float], stored: object) -> float:
    vector = stored.get(DENSE) if isinstance(stored, dict) else None
    if not isinstance(vector, list):
        return 0.0
    dot = sum(a * b for a, b in zip(query, vector, strict=True))
    norms = math.sqrt(sum(a * a for a in query)) * math.sqrt(sum(b * b for b in vector))
    return dot / norms if norms else 0.0


def _rerank_text(passage: Passage) -> str:
    return f"{passage.title}\n{passage.text}"


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 2)
