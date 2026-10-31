# JD fit

This checklist maps hiring themes to proof this repository does not claim yet. The skeleton only reserves a path. A later change has to produce the proof.

| Theme | Later proof | Scaffold |
| --- | --- | --- |
| Anthropic. Evals and reliable tool use | A checked-in eval that fails when answers drift, and tools with tests around them | `evals/`, `services/mcp` |
| OpenAI. A product a person can use | Upload, product configuration, and a session in the web app | `apps/web`, `services/api` |
| xAI. A system that runs | Compose starts the store, the index, the API, and the web app together | `docker-compose.yml` |
| Meta. Retrieval quality | Indexed documents and a measured score | `packages/rag`, `evals` |
| LiveKit. Realtime media | Screen share and voice through the worker | `services/agent`, compose profile `livekit` |
| Tesla FDE. Run it in someone else's environment | Documented setup, placeholder env, and CI on a clean machine | `README.md`, `.env.example`, `.github/workflows/ci.yml` |
