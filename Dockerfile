# Folio: API and built UI on one port. Pass keys at run time, never at build time:
#   docker build -t folio . && docker run --env-file .env -p 8787:8787 folio

FROM node:22-slim AS ui
WORKDIR /ui
COPY apps/companion/package.json apps/companion/package-lock.json ./
RUN npm ci
COPY apps/companion/ ./
RUN npm run build

FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project
COPY folio ./folio
RUN uv sync --locked
COPY --from=ui /ui/dist ./apps/companion/dist
RUN useradd --create-home folio && mkdir data && chown folio data
USER folio
ENV HOST=0.0.0.0 PORT=8787
EXPOSE 8787
CMD ["/app/.venv/bin/folio"]
