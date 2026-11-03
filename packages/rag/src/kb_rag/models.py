import os
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Protocol

from qdrant_client.models import SparseVector

# fastembed pulls in onnxruntime, so it loads with the first model. The agent
# imports this module for its types and never loads a model.
if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding, TextEmbedding
    from fastembed.rerank.cross_encoder import TextCrossEncoder


# One text at a time. A batch pads every text to the longest one, so on a
# 1,600-chunk upload the default of 256 took 7.8 GB, and 8 took more CPU than 1.
EMBED_BATCH = 1


class DenseEmbedder(Protocol):
    def size(self) -> int: ...

    def passages(self, texts: list[str]) -> list[list[float]]: ...

    def query(self, text: str) -> list[float]: ...


class SparseEmbedder(Protocol):
    def passages(self, texts: list[str]) -> list[SparseVector]: ...

    def query(self, text: str) -> SparseVector: ...


class Reranker(Protocol):
    def scores(self, query: str, texts: list[str]) -> list[float]: ...


def _threads() -> int | None:
    """ONNX threads per model. Unset lets onnxruntime use every core."""
    raw = os.environ.get("KB_EMBED_THREADS")
    if not raw:
        return None
    threads = int(raw)
    if threads < 1:
        raise ValueError("KB_EMBED_THREADS must be at least 1")
    return threads


@cache
def _dense(name: str) -> "TextEmbedding":
    from fastembed import TextEmbedding

    return TextEmbedding(name, threads=_threads())


@cache
def _sparse(name: str) -> "SparseTextEmbedding":
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(name)


@cache
def _reranker(name: str) -> "TextCrossEncoder":
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(name, threads=_threads())


@dataclass(frozen=True)
class FastEmbedDense:
    name: str

    def size(self) -> int:
        from fastembed import TextEmbedding

        return TextEmbedding.get_embedding_size(self.name)

    def passages(self, texts: list[str]) -> list[list[float]]:
        return [
            vector.tolist()
            for vector in _dense(self.name).passage_embed(texts, batch_size=EMBED_BATCH)
        ]

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
