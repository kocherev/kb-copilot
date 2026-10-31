# MCP server

This process speaks MCP over stdio. `search_kb` uses the same retrieval function as the agent. `get_product` reads `GET /products/{id}` on the API.

## Run

Start Postgres, Qdrant, and the API:

```bash
docker compose up --build
```

Create a product and upload its documents, as described in the repository README. From the repo root:

```bash
uv run --package kb-mcp kb-mcp
```

The process waits on stdin. `QDRANT_URL` defaults to `http://localhost:6333`. `API_URL` defaults to `http://localhost:8000`.

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

`search_kb` takes `query` and `product_id`. It returns `chunks` and `sources` for that product only. `get_product` takes `product_id` and returns the stored name, description, tone, and refusal rules.
