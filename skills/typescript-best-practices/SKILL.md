---
name: typescript-best-practices
description: >
  Rules for apps/web. App Router, strict TypeScript, and tests of the
  rendered screen. Use when editing the Next.js app.
---

# TypeScript in apps/web

`apps/web` is the only TypeScript package. `tsconfig.json` has `strict` on. ESLint is `eslint-config-next` for core web vitals and TypeScript.

## Components

Server components are the default. Add `"use client"` for state, event handlers, and LiveKit. Keep the data load on the server when the page already fetches the product.

The path alias is `@/`. Match the surrounding file. A test sits next to the component it renders (`session-start.test.tsx`).

Assert what the screen shows: heading text, the request body, the error string, the `Source:` label. Stub `fetch` at the call the component makes. Do not assert a private helper's call count.

## UI

Read `skills/interface/SKILL.md` before a visual change.

The button in `apps/web/src/components/ui/button.tsx` is Honest UI. Leave it, including the pressed scale. Tokens live in `apps/web/src/styles/honest-ui-theme.css`. `html` keeps `data-theme` and `data-gray-color`.

New primitives come from https://ds.asanshay.com/ before a hand-rolled component. Do not add a dependency for a few lines.

## Checks

```bash
pnpm --filter web lint
pnpm --filter web typecheck
pnpm --filter web test
```

`./scripts/check.sh` runs those, plus the Python checks and `make eval`. `pnpm build` is part of CI. Run it when the change touches routing or a server fetch.
