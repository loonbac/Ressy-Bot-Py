# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────
# Stage 1 — Build del frontend (Vite 8 / pnpm)
# Genera src/web/static que el backend FastAPI sirve como SPA.
# ─────────────────────────────────────────────────────────────
FROM node:22-bookworm-slim AS frontend

WORKDIR /app

# pnpm via corepack (pin a la versión del lockfile).
RUN corepack enable && corepack prepare pnpm@11.1.1 --activate

# Instalar deps con cache de capa: solo manifest + lock + workspace primero.
# --ignore-scripts: pnpm 11 bloquea postinstall de esbuild con exit 1; el
# binario llega vía el paquete optional @esbuild/<plataforma>, así que el
# postinstall es innecesario y la build de Vite funciona igual.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./frontend/
RUN cd frontend && pnpm install --frozen-lockfile --ignore-scripts

# Copiar el resto del frontend y construir.
# vite.config.ts → outDir '../src/web/static' (relativo a /app/frontend).
COPY frontend/ ./frontend/
RUN cd frontend && pnpm run build

# ─────────────────────────────────────────────────────────────
# Stage 2 — Runtime Python (bot Discord + FastAPI + Playwright)
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# uv: gestor de deps reproducible (usa uv.lock).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_PATH=/app/data/bot.db

WORKDIR /app

# Instalar dependencias Python primero (cache de capa: solo manifests).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copiar el código del backend (NO el frontend ni la build vieja).
COPY src/ ./src/

# Traer el frontend ya construido desde el stage 1.
COPY --from=frontend /app/src/web/static/ ./src/web/static/

# Instalar el proyecto en sí (entry point ressy-bot).
RUN uv sync --frozen --no-dev

# Chromium + dependencias de sistema para el scraper de Blackboard (Playwright).
# --with-deps instala las libs APT necesarias del navegador.
RUN uv run playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Datos persistentes (SQLite por plugin). En Coolify monta un volumen aquí.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8000

# Healthcheck: GET /healthz — liveness dedicado, estático, sin lógica de
# plugins/bot. Si el proceso atiende HTTP está vivo (200). Desacoplado de
# /api/status para que features futuras no causen falsos unhealthy.
# python:slim no trae curl/wget → urllib. Respeta $PORT.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz', timeout=4).status==200 else 1)"

# Arranque: bot Discord + uvicorn en el mismo event loop.
CMD ["uv", "run", "ressy-bot"]
