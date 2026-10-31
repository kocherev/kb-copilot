from llama_index.core import Document
from qdrant_client.models import Distance, VectorParams


def collection_name(product_id: str) -> str:
    cleaned = product_id.strip()
    if not cleaned:
        raise ValueError("product_id is required")
    if any(character.isspace() or character == "/" for character in cleaned):
        raise ValueError("product_id cannot contain whitespace or slashes")
    return f"kb_{cleaned}"


def document_from_passage(text: str, source: str) -> Document:
    cleaned = text.strip()
    cleaned_source = source.strip()
    if not cleaned:
        raise ValueError("text is required")
    if not cleaned_source:
        raise ValueError("source is required")
    return Document(text=cleaned, metadata={"source": cleaned_source})


def vector_params(size: int) -> VectorParams:
    if size <= 0:
        raise ValueError("size must be positive")
    return VectorParams(size=size, distance=Distance.COSINE)
