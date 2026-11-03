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
| Tutorial | How do I try it? | README quickstart, from `.env.example` through sign-up, an upload, and a first session |
| How-to | How do I do this one task? | `docs/setup.md`, `services/mcp/README.md`, `apps/desktop/README.md`, `evals/README.md` |
| Reference | What are the exact fields and commands? | Env vars, HTTP examples, the eval table, `AGENTS.md` commands |
| Explanation | Why is it shaped this way? | README "How it works", `docs/design.md`, `docs/case-study.md`, `docs/decisions` |

## README

Lead with what the program does, a screenshot, and what a user can do. The order after that is How it works, Quickstart, Evals, Replay and tracing, Desktop actions, MCP, Development, How this repo is maintained, License. Reference sections come after a reader can run it. Run every quickstart command from a clean `.env` before you change the quickstart.

The architecture diagram names `apps/web`, `services/api`, `services/agent`, `services/mcp`, `packages/rag`, `apps/desktop`, and `evals`. If the code path changes, change the diagram in the same commit. The worker does not load an embedding model or read Qdrant. It calls the API for `search_kb` and citations. A component that exists but is not called yet gets a dotted edge and a sentence saying so.

The eval table copies `make eval`. When the printout changes, replace the numbers from that printout.

A picture in the README says whether it is a screenshot or a live recording.

## Sentences

Public prose follows `skills/unslop/SKILL.md`. Sentence-case headings. One idea per sentence. Name the command, the status code, or the file.

Do not add a personal claim. The license statement points at `LICENSE`. Sample pages in `demo/docs` are original and use that same MIT license.
