# Lore: one container serving the API and the built web UI. FalkorDB runs separately
# (docker compose service, self-hosted, or FalkorDB Cloud via FALKORDB_HOST/PORT/USERNAME/PASSWORD).

FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/models LORE_UI_DIST=/app/frontend/dist LORE_DATA_DIR=/app/data
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
# bake the embedding model into the image so startup needs no download
RUN uv run python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
COPY data/ /app/data/
COPY --from=ui /ui/dist /app/frontend/dist
EXPOSE 8000
ENV LORE_SEED_ON_START=1
CMD ["sh", "-c", "uv run uvicorn lore.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
