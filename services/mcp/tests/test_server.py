import asyncio
import json
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest
from kb_mcp.server import build_server, qdrant_from_env
from kb_rag import Source, index_sources, read_directory
from kb_rag.testing import HASH_SETTINGS
from mcp import Client, StdioServerParameters
from mcp.server import MCPServer
from qdrant_client import AsyncQdrantClient

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


def _indexed() -> AsyncQdrantClient:
    async def build() -> AsyncQdrantClient:
        client = AsyncQdrantClient(":memory:")
        await index_sources(
            client, "demo", read_directory(DEMO), settings=HASH_SETTINGS
        )
        await index_sources(
            client,
            "other",
            [
                Source(
                    source="zephyr.md", text="Zephyr ships on Friday.", markdown=False
                )
            ],
            settings=HASH_SETTINGS,
        )
        return client

    return asyncio.run(build())


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
    return build_server(lambda: qdrant, api_url, HASH_SETTINGS)


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
    assert body["abstained"] is False
    assert "billing/refunds.md" in body["sources"]
    assert all(chunk["text"] and 0 < chunk["score"] <= 1 for chunk in body["chunks"])
    assert "zephyr.md" not in _text(result)
    assert all(
        not chunk["source"].startswith(("/", "file:")) for chunk in body["chunks"]
    )


def test_search_kb_abstains_on_a_question_the_docs_do_not_cover(
    server: MCPServer,
) -> None:
    result = _run(
        server,
        lambda client: client.call_tool(
            "search_kb",
            {"query": OTHER_QUESTION, "product_id": "demo"},
        ),
    )

    assert result.is_error is False
    assert result.structured_content == {"chunks": [], "sources": [], "abstained": True}


def test_search_kb_wrong_or_empty_product_is_a_tool_error(
    server: MCPServer,
) -> None:
    async def calls(client: Client):
        found = []
        for product_id in ("", " ", "a/b", "missing"):
            found.append(
                await client.call_tool(
                    "search_kb",
                    {"query": OTHER_QUESTION, "product_id": product_id},
                )
            )
        return found

    results = _run(server, calls)

    for result in results:
        assert result.is_error is True
        assert result.structured_content is None
        text = _text(result)
        assert "Zephyr" not in text
        assert "5 business days" not in text
    assert "no indexed documents" in _text(results[-1])


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
        env={
            "QDRANT_URL": "http://127.0.0.1:1",
            "QDRANT_API_KEY": "test-key",
            "API_URL": "http://127.0.0.1:1",
        },
    )

    async def listed() -> set[str]:
        async with Client(params) as client:
            result = await client.list_tools()
            return {tool.name for tool in result.tools}

    assert asyncio.run(listed()) == {"search_kb", "get_product"}


def test_qdrant_client_reads_the_url_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://qdrant.example:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")

    options = qdrant_from_env().init_options

    assert options["url"] == "https://qdrant.example:6333"
    assert options["api_key"] == "test-key"
