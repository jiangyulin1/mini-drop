# Mini-Drop Server Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml Makefile ./
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir \
    fastapi uvicorn pydantic grpcio grpcio-tools protobuf \
    sqlalchemy psycopg[binary] minio requests loguru pytest

COPY proto/ ./proto/
RUN cd proto && bash compile.sh

COPY server/ ./server/
COPY agent/mini_drop_agent/collectors/base.py ./agent/mini_drop_agent/collectors/

EXPOSE 8191 50051

CMD ["python", "-m", "server.app.main"]
