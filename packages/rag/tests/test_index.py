import pytest
from kb_rag.index import collection_name, document_from_passage, vector_params
from qdrant_client.models import Distance


def test_collection_name_uses_the_product_id() -> None:
    assert collection_name(" acme ") == "kb_acme"


def test_collection_name_rejects_empty_and_slashes() -> None:
    with pytest.raises(ValueError, match="required"):
        collection_name("  ")
    with pytest.raises(ValueError, match="slashes"):
        collection_name("acme/docs")


def test_document_keeps_source_metadata() -> None:
    document = document_from_passage("  refunds take 5 days  ", " handbook ")

    assert document.text == "refunds take 5 days"
    assert document.metadata == {"source": "handbook"}


def test_vector_params_are_cosine() -> None:
    params = vector_params(1536)

    assert params.size == 1536
    assert params.distance == Distance.COSINE


def test_vector_params_reject_non_positive_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        vector_params(0)
