from dataclasses import dataclass
from functools import cache
from typing import Protocol

from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client.models import SparseVector


class DenseEmbedder(Protocol):
    def size(self) -> int: ...

    def passages(self, texts: list[str]) -> list[list[float]]: ...

    def query(self, text: str) -> list[float]: ...


class SparseEmbedder(Protocol):
    def passages(self, texts: list[str]) -> list[SparseVector]: ...

    def query(self, text: str) -> SparseVector: ...


class Reranker(Protocol):
    def scores(self, query: str, texts: list[str]) -> list[float]: ...


@cache
def _dense(name: str) -> TextEmbedding:
    return TextEmbedding(name)


@cache
def _sparse(name: str) -> SparseTextEmbedding:
    return SparseTextEmbedding(name)


@cache
def _reranker(name: str) -> TextCrossEncoder:
    return TextCrossEncoder(name)


@dataclass(frozen=True)
class FastEmbedDense:
    name: str

    def size(self) -> int:
        return TextEmbedding.get_embedding_size(self.name)

    def passages(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in _dense(self.name).passage_embed(texts)]

    def query(self, text: str) -> list[float]:
        return next(iter(_dense(self.name).query_embed(text))).tolist()


@dataclass(frozen=True)
class FastEmbedSparse:
    name: str

    def passages(self, texts: list[str]) -> list[SparseVector]:
        return [
            SparseVector(indices=v.indices.tolist(), values=v.values.tolist())
            for v in _sparse(self.name).passage_embed(texts)
        ]

    def query(self, text: str) -> SparseVector:
        vector = next(iter(_sparse(self.name).query_embed(text)))
        return SparseVector(
            indices=vector.indices.tolist(), values=vector.values.tolist()
        )


@dataclass(frozen=True)
class FastEmbedReranker:
    name: str

    def scores(self, query: str, texts: list[str]) -> list[float]:
        return list(_reranker(self.name).rerank(query, texts))


@dataclass(frozen=True)
class RetrievalSettings:
    """Models and the abstain cutoff.

    A passage score is its dense cosine similarity to the query, or the
    cross-encoder score when a reranker is set. Search abstains when the best
    score is under abstain_threshold; None never abstains.
    """

    dense: DenseEmbedder = FastEmbedDense("google/embeddinggemma-300m")
    sparse: SparseEmbedder = FastEmbedSparse("Qdrant/bm25")
    reranker: Reranker | None = None
    # Chosen by `make bakeoff`; see docs/decisions/0001-retrieval.md.
    abstain_threshold: float | None = 0.379
    candidates: int = 20


DEFAULT_SETTINGS = RetrievalSettings()
