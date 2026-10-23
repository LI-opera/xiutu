# API and worker image. Build from the repository root (see compose.yaml).
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.11.32

WORKDIR /app
# Dependencies first, so code changes do not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && rm -rf /root/.cache

COPY alembic.ini ./
COPY backend backend
COPY migrations migrations
COPY resources resources
COPY scripts scripts
COPY deploy/docker/backend-entry.sh deploy/docker/backend-entry.sh

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/backend
RUN useradd --uid 10001 --no-create-home xiutu \
    && mkdir -p /app/.local-data && chown xiutu /app/.local-data
USER xiutu

ENTRYPOINT ["sh", "deploy/docker/backend-entry.sh"]
CMD ["api"]
