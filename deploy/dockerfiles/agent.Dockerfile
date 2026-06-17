# Mini-Drop Agent Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    linux-tools-generic \
    linux-tools-common \
    bpftrace \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir py-spy grpcio protobuf

WORKDIR /app

COPY proto/ ./proto/
RUN cd proto && bash compile.sh

COPY agent/ ./agent/
COPY server/app/generated/ ./server/app/generated/

CMD ["python", "-m", "agent.mini_drop_agent.main"]
