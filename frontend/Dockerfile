# syntax=docker/dockerfile:1.7
# ── Stage 1: Compile (Python) ─────────────────────────────────────────
FROM python:3.11-slim AS compiler

WORKDIR /build

COPY frontend/compiler ./compiler
COPY marketplace.yaml /config/marketplace.yaml
COPY openapi/generated_openapi.json /config/openapi.json

RUN pip install --no-cache-dir pyyaml>=6.0 rich>=13.9.0

RUN python -m compiler generate \
    --openapi /config/openapi.json \
    --marketplace /config/marketplace.yaml \
    --output /build/app

# ── Stage 2: Install + Build (Node) ──────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=compiler /build/app/package.json /build/app/package-lock.json* ./
RUN npm ci

COPY --from=compiler /build/app ./
RUN npm run build

# ── Stage 3: Run ─────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["npm", "start"]
