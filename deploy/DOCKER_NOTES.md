# Docker Deployment Notes

## MinIO endpoints

`MINIO_ENDPOINT` is the internal Docker-network address used by Server and Agent, for example `minio:9000`.

`MINIO_PUBLIC_ENDPOINT` is the browser-facing address embedded in presigned URLs. Local Docker Compose uses `localhost:9000`, so links opened by the Web UI can reach MinIO through the published host port.

For remote deployments, set `MINIO_PUBLIC_ENDPOINT` to a domain or IP that the user's browser can reach.

Example for a VM whose address is `172.24.188.165`:

```bash
MINIO_PUBLIC_ENDPOINT=172.24.188.165:9000
```

## Host profiling prerequisites

The Agent container runs with `privileged` and `pid: host`, but Linux still needs to allow `perf` sampling on the host. For demo VMs, set:

```bash
echo 'kernel.perf_event_paranoid=1' | sudo tee /etc/sysctl.d/99-mini-drop.conf
sudo sysctl -p /etc/sysctl.d/99-mini-drop.conf
```

MinIO also refuses uploads when the host disk is almost full. Keep at least 1 GB free for short smoke tests, and more for longer profiling sessions.

## Local/offline demo mode

When Docker cannot pull `node:20-alpine`, `postgres:16`, or MinIO images, use the local override:

```bash
npm --prefix web run build
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build server agent web
```

This mode uses SQLite and a shared artifact volume. It is for local validation, not a replacement for the full PostgreSQL + MinIO deployment.
