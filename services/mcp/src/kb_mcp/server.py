"""stdio MCP server for search_kb and get_product."""

import os
from collections.abc import Callable
from functools import cache
from typing import Annotated

from kb_agent.product import fetch_product
from kb_agent.retrieve import search_kb as lookup_kb
from kb_rag.index import collection_name
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)


class KbChunk(BaseModel):
    """One retrieved passage."""

    source_url: str
    text: str


class KbSearchResult(BaseModel):
    """Chunks from one product and the source URLs they came from."""

    chunks: list[KbChunk]
    sources: list[str]


class ProductConfig(BaseModel):
    """Name, description, tone, and refusal rules for one product."""

    id: str
    name: str
    description: str
    tone: str
    refusal_rules: str


def build_server(
    qdrant: Callable[[], QdrantClient],
    api_url: str,
) -> MCPServer:
    mcp = MCPServer(
        "kb-copilot",
        instructions=(
            "Search one product's knowledge base and read that product's config."
        ),
    )

    @mcp.tool(annotations=_READ)
    def search_kb(
        query: Annotated[str, Field(description="Question to look up.")],
        product_id: Annotated[
            str, Field(description="Product whose documents to search.")
        ],
    ) -> KbSearchResult:
        """Search one product's indexed documents for matching passages."""
        try:
            collection_name(product_id)
        except ValueError:
            # shortcut: bad ids match nothing. Revisit if callers need the error.
            return KbSearchResult(chunks=[], sources=[])
        found = lookup_kb(qdrant(), product_id, query)
        return KbSearchResult(
            chunks=[
                KbChunk(source_url=hit.source_url, text=hit.text) for hit in found.hits
            ],
            sources=found.source_urls(),
        )

    @mcp.tool(annotations=_READ)
    def get_product(
        product_id: Annotated[str, Field(description="Product id from the API.")],
    ) -> ProductConfig:
        """Read one product's stored config."""
        cleaned = product_id.strip()
        if not cleaned:
            raise ToolError("product_id is required")
        try:
            product = fetch_product(api_url, cleaned)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return ProductConfig(
            id=cleaned,
            name=product.name,
            description=product.description,
            tone=product.tone,
            refusal_rules=product.refusal_rules,
        )

    return mcp


def server_from_env() -> MCPServer:
    url = os.environ.get("QDRANT_URL") or "http://localhost:6333"

    @cache
    def qdrant() -> QdrantClient:
        return QdrantClient(url=url)

    return build_server(qdrant, os.environ.get("API_URL", "http://localhost:8000"))


mcp = server_from_env()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
