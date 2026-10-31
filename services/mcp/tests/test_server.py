import asyncio
import json
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest
from kb_mcp.server import build_server
from kb_rag.pipeline import index_sources
from kb_rag.sources import Source, iter_documents, read_source
from mcp import Client, StdioServerParameters
from mcp.server import MCPServer
from qdrant_client import QdrantClient

DEMO = Path(__file__).resolve().parents[3] / "demo" / "docs"
REFUND_QUESTION = "How long do refunds take?"
OTHER_QUESTION = "When does zephyr ship?"
PRODUCT = {
    "id": "demo",
    "name": "Northstar Desk",
    "description": "Northstar Desk answers questions about the workspace.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a policy that is not in the docs.",
}


def _run(server: MCPServer, call):
    async def run():
        async with Client(server, raise_exceptions=True) as client:
            return await call(client)

    return asyncio.run(run())


def _indexed() -> QdrantClient:
    client = QdrantClient(":memory:")
    index_sources(
        client,
        "demo",
        [read_source(path) for path in iter_documents(DEMO)],
    )
    index_sources(
        client,
        "other",
        [
            Source(
                source_url="file:///docs/zephyr.md",
                text="Zephyr ships on Friday.",
                markdown=False,
            )
        ],
    )
    return client


def _text(result: object) -> str:
    content = getattr(result, "content", [])
    return "\n".join(getattr(block, "text", "") for block in content)


@pytest.fixture
def api_url() -> Iterator[str]:
    products = {"demo": PRODUCT}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            product_id = unquote(urlparse(self.path).path.removeprefix("/products/"))
            found = products.get(product_id)
            if found is None:
                payload = b'{"detail":"product not found"}'
                status = 404
            else:
                payload = json.dumps(found).encode()
                status = 200
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}"
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def server(api_url: str) -> MCPServer:
    qdrant = _indexed()
    return build_server(lambda: qdrant, api_url)


def test_client_lists_search_kb_and_get_product(server: MCPServer) -> None:
    listed = _run(server, lambda client: client.list_tools())
    by_name = {tool.name: tool for tool in listed.tools}

    assert set(by_name) == {"search_kb", "get_product"}
    assert set(by_name["search_kb"].input_schema["required"]) == {
        "query",
        "product_id",
    }
    assert set(by_name["get_product"].input_schema["required"]) == {"product_id"}
    assert by_name["search_kb"].description
    assert by_name["get_product"].description


def test_search_kb_returns_a_demo_billing_passage(server: MCPServer) -> None:
    result = _run(
        server,
        lambda client: client.call_tool(
            "search_kb",
            {"query": REFUND_QUESTION, "product_id": "demo"},
        ),
    )

    assert result.is_error is False
    body = result.structured_content
    assert body is not None
    assert any("billing.md" in source for source in body["sources"])
    assert any("5 business days" in chunk["text"] for chunk in body["chunks"])
    assert "5 business days" in _text(result)
    assert "zephyr.md" not in _text(result)
    assert all(chunk["text"] for chunk in body["chunks"])


def test_search_kb_wrong_or_empty_product_returns_no_other_chunks(
    server: MCPServer,
) -> None:
    async def calls(client: Client):
        found = []
        for product_id in ("", " ", "missing"):
            found.append(
                await client.call_tool(
                    "search_kb",
                    {"query": OTHER_QUESTION, "product_id": product_id},
                )
            )
        return found

    results = _run(server, calls)

    for result in results:
        assert result.is_error is False
        assert result.structured_content == {"chunks": [], "sources": []}
        text = _text(result)
        assert "Zephyr" not in text
        assert "zephyr.md" not in text
        assert "5 business days" not in text


def test_get_product_returns_the_stored_config(server: MCPServer) -> None:
    result = _run(
        server,
        lambda client: client.call_tool("get_product", {"product_id": "demo"}),
    )

    assert result.is_error is False
    assert result.structured_content == PRODUCT
    assert "Northstar Desk" in _text(result)


def test_get_product_for_a_missing_id_does_not_return_another_product(
    server: MCPServer,
) -> None:
    async def calls(client: Client):
        missing = await client.call_tool("get_product", {"product_id": "missing"})
        empty = await client.call_tool("get_product", {"product_id": " "})
        return [missing, empty]

    missing, empty = _run(server, calls)

    assert missing.is_error is True
    assert empty.is_error is True
    for result in (missing, empty):
        text = _text(result)
        assert "Northstar Desk" not in text
        assert "Do not invent a policy" not in text
        assert result.structured_content is None


def test_stdio_client_lists_the_same_tools() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "kb_mcp"],
        env={"QDRANT_URL": "http://127.0.0.1:1", "API_URL": "http://127.0.0.1:1"},
    )

    async def listed() -> set[str]:
        async with Client(params) as client:
            result = await client.list_tools()
            return {tool.name for tool in result.tools}

    assert asyncio.run(listed()) == {"search_kb", "get_product"}
