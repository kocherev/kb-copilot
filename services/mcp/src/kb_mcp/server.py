"""stdio MCP server for search_kb and get_product."""

import asyncio
import json
import os
from collections.abc import Callable
from functools import cache
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from kb_rag import (
    DEFAULT_SETTINGS,
    KB_COLLECTION,
    RetrievalSettings,
    search,
    validate_product_id,
)
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)


class KbChunk(BaseModel):
    """One retrieved passage."""

    source: str
    title: str
    anchor: str
    text: str
    score: float


class KbSearchResult(BaseModel):
    """Passages from one product, or abstained when none is relevant."""

    chunks: list[KbChunk]
    sources: list[str]
    abstained: bool


class ProductConfig(BaseModel):
    """Name, description, tone, and refusal rules for one product."""

    id: str
    name: str
    description: str
    tone: str
    refusal_rules: str


def fetch_product(api_url: str, product_id: str, token: str = "") -> ProductConfig:
    request_url = f"{api_url.rstrip('/')}/products/{quote(product_id, safe='')}"
    request = Request(request_url, headers={"X-Internal-Token": token} if token else {})
    try:
        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode())
    except HTTPError as exc:
        raise ToolError(f"product config returned {exc.code}") from exc
    except URLError as exc:
        raise ToolError("product config is unreachable") from exc
    if not isinstance(body, dict):
        raise ToolError("product config must be an object")
    try:
        return ProductConfig.model_validate({**body, "id": product_id})
    except ValidationError as exc:
        raise ToolError("product config is incomplete") from exc


async def _has_documents(client: AsyncQdrantClient, product_id: str) -> bool:
    if not await client.collection_exists(KB_COLLECTION):
        return False
    found = await client.count(
        collection_name=KB_COLLECTION,
        count_filter=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value=product_id))]
        ),
        exact=False,
    )
    return found.count > 0


def build_server(
    qdrant: Callable[[], AsyncQdrantClient],
    api_url: str,
    settings: RetrievalSettings = DEFAULT_SETTINGS,
    *,
    internal_token: str = "",
) -> MCPServer:
    mcp = MCPServer(
        "kb-copilot",
        instructions=(
            "Search one product's knowledge base and read that product's config."
        ),
    )

    @mcp.tool(annotations=_READ)
    async def search_kb(
        query: Annotated[str, Field(description="Question to look up.")],
        product_id: Annotated[
            str, Field(description="Product whose documents to search.")
        ],
    ) -> KbSearchResult:
        """Search one product's indexed documents for matching passages."""
        try:
            product = validate_product_id(product_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        client = qdrant()
        if not await _has_documents(client, product):
            raise ToolError(f"product {product} has no indexed documents")
        found = await search(client, product, query, settings=settings)
        sources: list[str] = []
        for passage in found.passages:
            if passage.source not in sources:
                sources.append(passage.source)
        return KbSearchResult(
            chunks=[
                KbChunk(
                    source=passage.source,
                    title=passage.title,
                    anchor=passage.anchor,
                    text=passage.text,
                    score=passage.score,
                )
                for passage in found.passages
            ],
            sources=sources,
            abstained=found.abstained,
        )

    @mcp.tool(annotations=_READ)
    async def get_product(
        product_id: Annotated[str, Field(description="Product id from the API.")],
    ) -> ProductConfig:
        """Read one product's stored config."""
        cleaned = product_id.strip()
        if not cleaned:
            raise ToolError("product_id is required")
        return await asyncio.to_thread(fetch_product, api_url, cleaned, internal_token)

    return mcp


def qdrant_from_env() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=os.environ.get("QDRANT_URL") or "http://localhost:6333",
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )


def server_from_env() -> MCPServer:
    return build_server(
        cache(qdrant_from_env),
        os.environ.get("API_URL", "http://localhost:8000"),
        internal_token=os.environ.get("INTERNAL_API_TOKEN", ""),
    )


def main() -> None:
    server_from_env().run()


if __name__ == "__main__":
    main()
