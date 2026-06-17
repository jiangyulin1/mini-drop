FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    bpftrace \
    curl \
    linux-perf \
    perl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir grpcio grpcio-tools protobuf py-spy

WORKDIR /app
COPY proto/ ./proto/
RUN cd proto && bash compile.sh
COPY agent/ ./agent/
COPY analyzer/ ./analyzer/
COPY server/app/generated/ ./server/app/generated/

CMD ["python", "-m", "agent.mini_drop_agent.main"]
