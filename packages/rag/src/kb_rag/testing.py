"""A deterministic, model-free embedder for tests that do not need FastEmbed."""

import hashlib
import math
import re
from dataclasses import dataclass

from qdrant_client.models import SparseVector

from kb_rag.models import RetrievalSettings

_TOKEN = re.compile(r"[a-z0-9]+")


def _buckets(text: str) -> list[tuple[int, float]]:
    found: list[tuple[int, float]] = []
    for token in _TOKEN.findall(text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        found.append((int.from_bytes(digest[:4], "little") & 0x7FFFFFFF, sign))
    return found


@dataclass(frozen=True)
class HashDense:
    """Signed sha256 token buckets. Shares words, not meaning."""

    dimensions: int = 384

    def size(self) -> int:
        return self.dimensions

    def passages(self, texts: list[str]) -> list[list[float]]:
        return [self.query(text) for text in texts]

    def query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for index, sign in _buckets(text):
            vector[index % self.dimensions] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


@dataclass(frozen=True)
class HashSparse:
    """Hashed term counts; Qdrant applies IDF."""

    def passages(self, texts: list[str]) -> list[SparseVector]:
        return [self.query(text) for text in texts]

    def query(self, text: str) -> SparseVector:
        counts: dict[int, float] = {}
        for index, _sign in _buckets(text):
            counts[index] = counts.get(index, 0.0) + 1.0
        indices = sorted(counts)
        return SparseVector(indices=indices, values=[counts[i] for i in indices])


HASH_SETTINGS = RetrievalSettings(
    dense=HashDense(), sparse=HashSparse(), reranker=None, abstain_threshold=0.2
)
