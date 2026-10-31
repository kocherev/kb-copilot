---
name: technical-writing
description: >
  Structure public docs as a tutorial, a how-to, a reference, or an
  explanation. Use when editing the README or other docs a reader keeps.
---

# Technical writing

Pick one of the four modes before writing. Mixing them in one section makes the steps hard to follow.

| Mode | Question it answers | In this repo |
| --- | --- | --- |
| Tutorial | How do I try it? | README quickstart, from `.env.example` through `docker compose up` |
| How-to | How do I do this one task? | `services/mcp/README.md`, `evals/README.md` |
| Reference | What are the exact fields and commands? | Env vars, HTTP examples, the eval table, `AGENTS.md` commands |
| Explanation | Why is it shaped this way? | README architecture diagram |

## README

Lead with what the program does. Then the diagram, the quickstart, the demo, the eval table, and the MCP client. Reference sections come after a reader can run it.

The architecture diagram names `apps/web`, `services/api`, `services/agent`, `services/mcp`, `packages/rag`, and `evals`. If the code path changes, change the diagram in the same commit. The worker searches Qdrant in-process. It does not call the API for `search_kb`.

The eval table copies `make eval`. When the printout changes, replace the numbers from that printout.

Demo pictures show the session screen. If they are not a live recording, say that, and say that a live capture needs LiveKit credentials and a model key.

## Sentences

Public prose follows `skills/unslop/SKILL.md`. Sentence-case headings. One idea per sentence. Name the command, the status code, or the file.

Do not add a personal claim. The license statement points at `LICENSE`. Sample pages in `demo/docs` are original and use that same MIT license.

Do not name an editor or a coding agent in the README, a skill, or a commit message.
