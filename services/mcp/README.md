# MCP server

This process speaks MCP over stdio. `search_kb` calls `search` in `packages/rag`, the same hybrid query and abstain step the agent uses. `get_product` reads `GET /products/{id}` on the API.

## Run

Start the stack, then create a product and upload its documents, as in the Quickstart of the repository README. The product id is the UUID the API returned. From the repo root:

```bash
uv run --package kb-mcp kb-mcp
```

The process waits on stdin. It needs Python 3.12 and uv on the host. The first `search_kb` call downloads the embedding models, about 1.2 GB, unless they are already cached. Set `FASTEMBED_CACHE_PATH` to choose where.

| Variable | Default | Used by |
| --- | --- | --- |
| `QDRANT_URL` | `http://localhost:6333` | `search_kb`. Change it when you changed `QDRANT_PORT` |
| `QDRANT_API_KEY` | none | `search_kb`, sent when set |
| `API_URL` | `http://localhost:8000` | `get_product`. Change it when you changed `API_PORT` |

## Connect a client

The client starts the process. Stdout is the protocol. Set the project directory to this repo so `uv` can see the workspace.

```json
{
  "mcpServers": {
    "kb-copilot": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/kb-copilot",
        "--package",
        "kb-mcp",
        "kb-mcp"
      ],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Tools

`search_kb` takes `query` and `product_id`. It returns `chunks` (source, title, anchor, text, score), `sources`, and `abstained` for that product only. `abstained` is true and `chunks` is empty when no passage clears the abstain threshold. A malformed product id, or one with no indexed documents, is a tool error. `get_product` takes `product_id` and returns the stored name, description, tone, and refusal rules.

## Known limit: `get_product` returns 401

The API requires a sign-in for `GET /products/{id}`. A service may instead send the header `X-Internal-Token` with the API's `INTERNAL_API_TOKEN`, which the agent does. This server sends no credentials and does not read `INTERNAL_API_TOKEN`, so `get_product` returns the tool error `product config returned 401` on the current code. `search_kb` does not call the API and is not affected.
