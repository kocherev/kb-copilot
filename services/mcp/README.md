# MCP server

This process speaks MCP over stdio. `search_kb` calls `search` in `packages/rag`, the same hybrid query and abstain step the agent uses. `get_product` reads `GET /products/{id}` on the API.

## Run

Start Postgres, Qdrant, and the API:

```bash
docker compose up --build
```

Create a product and upload its documents, as described in the repository README. From the repo root:

```bash
uv run --package kb-mcp kb-mcp
```

The process waits on stdin. `QDRANT_URL` defaults to `http://localhost:6333`. `QDRANT_API_KEY` is sent when set. `API_URL` defaults to `http://localhost:8000`.

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

`search_kb` takes `query` and `product_id`. It returns `chunks` (source, title, anchor, text, score), `sources`, and `abstained` for that product only. `abstained` is true and `chunks` is empty when no passage clears the abstain threshold. A malformed product id, or one with no indexed documents, is a tool error. `get_product` takes `product_id` and returns the stored name, description, tone, and refusal rules.
