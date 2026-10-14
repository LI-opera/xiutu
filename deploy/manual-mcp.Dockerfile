FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY backend /app/backend
ENV PYTHONPATH=/app/backend PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MANUAL_MCP_CONFIG=/run/secrets/manual-mcp.json
USER 10001:10001
CMD ["python", "-B", "-m", "uvicorn", "app.mcp_server.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8031", "--no-access-log", "--log-level", "warning"]
