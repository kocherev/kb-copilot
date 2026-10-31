import hashlib
import math
import re

from qdrant_client.models import SparseVector

DENSE_SIZE = 384
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    found = _TOKEN.findall(text.lower())
    return found or ["empty"]


def dense_vector(text: str) -> list[float]:
    vector = [0.0] * DENSE_SIZE
    for token in tokens(text):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "little") % DENSE_SIZE
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def sparse_vector(text: str) -> SparseVector:
    counts: dict[int, float] = {}
    for token in tokens(text):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "little") & 0x7FFFFFFF
        counts[index] = counts.get(index, 0.0) + 1.0
    indices = sorted(counts)
    return SparseVector(indices=indices, values=[counts[index] for index in indices])
