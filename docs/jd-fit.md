# JD fit

This checklist maps hiring themes to the proof still left. Paths that already exist are named in the scaffold column.

| Theme | Later proof | Scaffold |
| --- | --- | --- |
| Anthropic. Evals and reliable tool use | A checked-in eval that fails when answers drift | `search_kb` with tests in `services/agent`. `evals/` is still exact match only |
| OpenAI. A product a person can use | A call placed with a real model key | `apps/web` starts a session. `POST /sessions` returns a token. The worker speaks through STT, an LLM, and TTS |
| xAI. A system that runs | Compose starts the store, the index, the API, the web app, and the worker together | `docker-compose.yml` |
| Meta. Retrieval quality | Indexed documents and a measured score | `packages/rag`, `evals` |
| LiveKit. Realtime media | A call placed with LiveKit keys, microphone, and screen share | `POST /sessions`, `services/agent`, `/products/{id}/session`, compose profile `livekit` |
| Tesla FDE. Run it in someone else's environment | Documented setup, placeholder env, and CI on a clean machine | `README.md`, `.env.example`, `.github/workflows/ci.yml` |
