# Mini-Drop Server Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY server/ ./server/
COPY agent/ ./agent/
COPY analyzer/ ./analyzer/

RUN pip install --no-cache-dir -e .

COPY proto/ ./proto/
RUN cd proto && bash compile.sh

EXPOSE 8191 50051

CMD ["python", "-m", "server.app.main"]
