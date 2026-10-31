FROM node:22-bookworm-slim

RUN corepack enable && corepack prepare pnpm@10.33.4 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web apps/web

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN pnpm --filter web build

EXPOSE 3000

CMD ["pnpm", "--filter", "web", "exec", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
