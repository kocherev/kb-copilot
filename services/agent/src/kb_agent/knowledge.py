"""The agent's knowledge base: two internal routes on the API.

The API owns the embedding models, so the agent loads none.
"""

import httpx
from pydantic import BaseModel

# The wait is a pause in the user's conversation, so give up early.
TIMEOUT = httpx.Timeout(5.0, connect=2.0)


class Passage(BaseModel, frozen=True):
    id: str
    title: str
    source: str
    anchor: str
    text: str
    score: float


class SearchResult(BaseModel, frozen=True):
    passages: tuple[Passage, ...]
    abstained: bool
    timings_ms: dict[str, float]


class Supported(BaseModel):
    passage_ids: list[str]


def api_client(api_url: str, token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=api_url, headers={"X-Internal-Token": token}, timeout=TIMEOUT
    )


class Knowledge:
    """One product's knowledge base. Keep one per session and close it at the end."""

    def __init__(self, product_id: str, client: httpx.AsyncClient) -> None:
        self.product_id = product_id
        self.client = client

    async def search(self, query: str) -> SearchResult:
        reply = await self.client.post(
            "/internal/search",
            json={"product_id": self.product_id, "query": query, "limit": 5},
        )
        reply.raise_for_status()
        return SearchResult.model_validate(reply.json())

    async def supported(self, answer: str, passage_ids: list[str]) -> list[str]:
        """The passage ids a sentence of the answer restates."""
        reply = await self.client.post(
            "/internal/citations",
            json={
                "product_id": self.product_id,
                "answer": answer,
                "passage_ids": passage_ids,
            },
        )
        reply.raise_for_status()
        return Supported.model_validate(reply.json()).passage_ids

    async def aclose(self) -> None:
        await self.client.aclose()
