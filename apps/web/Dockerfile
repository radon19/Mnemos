# syntax=docker/dockerfile:1.7
# Build context is the repository root: the web app depends on @mnemos/crypto.
FROM node:26-alpine AS deps

ENV PNPM_HOME=/pnpm
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@12.15.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY apps/mcp/package.json ./apps/mcp/package.json
COPY packages/crypto/package.json ./packages/crypto/package.json
COPY packages/crypto-vectors/package.json ./packages/crypto-vectors/package.json
RUN pnpm install --frozen-lockfile

FROM deps AS builder

WORKDIR /app
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @mnemos/crypto build \
  && pnpm --filter @mnemos/web build

FROM node:26-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/apps/web/package.json ./package.json
COPY --from=builder /app/apps/web/next.config.ts ./next.config.ts

USER node
EXPOSE 3000
CMD ["node", "./node_modules/next/dist/bin/next", "start", "--port", "3000"]
