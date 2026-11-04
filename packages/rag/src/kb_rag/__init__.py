"""Parse, chunk, index, and search product documents in Qdrant."""

from kb_rag.citations import supported_ids
from kb_rag.models import (
    DEFAULT_SETTINGS,
    FastEmbedDense,
    FastEmbedReranker,
    FastEmbedSparse,
    RetrievalSettings,
)
from kb_rag.pipeline import (
    KB_COLLECTION,
    NOT_IN_DOCS,
    IndexModelMismatch,
    Passage,
    SearchResult,
    delete_source,
    index_sources,
    search,
    should_abstain,
    validate_product_id,
)
from kb_rag.sources import Source, read_directory, source_from_bytes

__all__ = [
    "DEFAULT_SETTINGS",
    "FastEmbedDense",
    "FastEmbedReranker",
    "FastEmbedSparse",
    "IndexModelMismatch",
    "KB_COLLECTION",
    "NOT_IN_DOCS",
    "Passage",
    "RetrievalSettings",
    "SearchResult",
    "Source",
    "delete_source",
    "index_sources",
    "read_directory",
    "search",
    "should_abstain",
    "source_from_bytes",
    "supported_ids",
    "validate_product_id",
]
