FROM node:22-bookworm-slim AS builder

RUN corepack enable && corepack prepare pnpm@10.33.4 --activate

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web apps/web

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN pnpm --filter web build

FROM node:22-bookworm-slim

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
# The standalone server binds to $HOSTNAME, which Docker sets to the container id.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=builder --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /app/apps/web/.next/static apps/web/.next/static

USER node

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
