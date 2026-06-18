FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    bpftrace \
    curl \
    linux-perf \
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

CMD ["python", "-m", "agent.mini_drop_agent.main"]
