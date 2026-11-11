# syntax=docker/dockerfile:1.7
# Build context is the repository root: the web app depends on @mnemos/crypto.
FROM node:26-alpine AS deps

ENV PNPM_HOME=/pnpm
ENV PATH="$PNPM_HOME:$PATH"
# Node 25 and later ship without corepack, so pnpm is installed directly.
RUN npm install -g pnpm@12.15.0

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY apps/mcp/package.json ./apps/mcp/package.json
COPY packages/crypto/package.json ./packages/crypto/package.json
COPY packages/crypto-vectors/package.json ./packages/crypto-vectors/package.json
RUN pnpm install --frozen-lockfile

FROM deps AS builder

# The public configuration is read at build time, so the build arguments have
# to be declared and passed into the environment.
ARG NEXT_PUBLIC_BROKER_URL
ARG NEXT_PUBLIC_CONTRACT_ID
ARG NEXT_PUBLIC_NEAR_NETWORK
ARG NEXT_PUBLIC_NEAR_RPC_URL
ARG NEXT_PUBLIC_BROKER_RECIPIENT
ARG NEXT_PUBLIC_DEMO_MODE
ENV NEXT_PUBLIC_BROKER_URL=$NEXT_PUBLIC_BROKER_URL \
    NEXT_PUBLIC_CONTRACT_ID=$NEXT_PUBLIC_CONTRACT_ID \
    NEXT_PUBLIC_NEAR_NETWORK=$NEXT_PUBLIC_NEAR_NETWORK \
    NEXT_PUBLIC_NEAR_RPC_URL=$NEXT_PUBLIC_NEAR_RPC_URL \
    NEXT_PUBLIC_BROKER_RECIPIENT=$NEXT_PUBLIC_BROKER_RECIPIENT \
    NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
COPY . .
RUN pnpm --filter @mnemos/crypto build \
  && pnpm --filter @mnemos/web build

FROM node:26-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app

COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
