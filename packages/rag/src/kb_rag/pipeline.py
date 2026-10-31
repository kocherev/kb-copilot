import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Modifier,
    PointStruct,
    Prefetch,
    SparseVectorParams,
)

from kb_rag.chunk import chunk_text
from kb_rag.embed import DENSE_SIZE, dense_vector, sparse_vector
from kb_rag.index import collection_name, vector_params
from kb_rag.sources import Source

# One shared collection. product_id is a payload filter, not a collection name.
KB_COLLECTION = "kb_chunks"


def ensure_collection(client: QdrantClient) -> None:
    if client.collection_exists(KB_COLLECTION):
        return
    # shortcut: shared sparse IDF. Revisit when each product needs its own.
    client.create_collection(
        collection_name=KB_COLLECTION,
        vectors_config={"dense": vector_params(DENSE_SIZE)},
        sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
    )


def _product_source_filter(product_id: str, source_url: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="product_id", match=MatchValue(value=product_id)),
            FieldCondition(key="source_url", match=MatchValue(value=source_url)),
        ]
    )


def index_sources(client: QdrantClient, product_id: str, sources: list[Source]) -> int:
    collection_name(product_id)
    cleaned_product = product_id.strip()
    ensure_collection(client)
    # shortcut: mid-folder failure keeps earlier files. Revisit when atomic.
    count = 0
    for source in sources:
        chunks = chunk_text(source.text, markdown=source.markdown)
        if not chunks:
            raise ValueError(f"{source.source_url} produced no chunks")
        client.delete(
            collection_name=KB_COLLECTION,
            points_selector=_product_source_filter(cleaned_product, source.source_url),
        )
        points: list[PointStruct] = []
        for index, text in enumerate(chunks):
            point_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{cleaned_product}|{source.source_url}|{index}",
            )
            points.append(
                PointStruct(
                    id=str(point_id),
                    vector={
                        "dense": dense_vector(text),
                        "bm25": sparse_vector(text),
                    },
                    payload={
                        "product_id": cleaned_product,
                        "source_url": source.source_url,
                        "text": text,
                    },
                )
            )
        client.upsert(collection_name=KB_COLLECTION, points=points)
        count += len(points)
    return count


def search_chunks(
    client: QdrantClient, product_id: str, query: str, limit: int = 5
) -> list[dict[str, str]]:
    collection_name(product_id)
    cleaned_product = product_id.strip()
    ensure_collection(client)
    product_filter = Filter(
        must=[FieldCondition(key="product_id", match=MatchValue(value=cleaned_product))]
    )
    prefetch_limit = max(limit, 8)
    hits = client.query_points(
        collection_name=KB_COLLECTION,
        prefetch=[
            Prefetch(
                query=dense_vector(query),
                using="dense",
                limit=prefetch_limit,
                filter=product_filter,
            ),
            Prefetch(
                query=sparse_vector(query),
                using="bm25",
                limit=prefetch_limit,
                filter=product_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    found: list[dict[str, str]] = []
    for point in hits.points:
        payload = point.payload or {}
        found.append(
            {
                "product_id": str(payload.get("product_id", "")),
                "source_url": str(payload.get("source_url", "")),
                "text": str(payload.get("text", "")),
            }
        )
    return found
