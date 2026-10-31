# JD fit

This checklist maps hiring themes to the proof still left. Paths that already exist are named in the scaffold column.

| Theme | Later proof | Scaffold |
| --- | --- | --- |
| Anthropic. Evals and reliable tool use | A checked-in eval that fails when answers drift, and tools with tests around them | `evals/`, `services/mcp` |
| OpenAI. A product a person can use | A live session in the web app | `apps/web` creates a product, edits its config, and uploads documents. `services/api` stores that config |
| xAI. A system that runs | Compose starts the store, the index, the API, and the web app together | `docker-compose.yml` |
| Meta. Retrieval quality | Indexed documents and a measured score | `packages/rag`, `evals` |
| LiveKit. Realtime media | Screen share and voice through the worker | `services/agent`, compose profile `livekit` |
| Tesla FDE. Run it in someone else's environment | Documented setup, placeholder env, and CI on a clean machine | `README.md`, `.env.example`, `.github/workflows/ci.yml` |
