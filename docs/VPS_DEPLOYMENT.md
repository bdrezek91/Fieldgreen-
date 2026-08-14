# VPS Deployment

Status: PHASE 1 infrastructure baseline.

Target: Linux VPS with Git, Docker Engine and the Docker Compose plugin.

```bash
git clone <future-repository-url>
cd ai-trading-lab
cp .env.example .env
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

The current `research` service exposes no port, runs as an unprivileged user, has all Linux
capabilities dropped, uses a read-only filesystem and has networking disabled. It is a safe
infrastructure heartbeat only.

The base image is version-pinned to Python 3.12.14 slim-bookworm. A digest must be recorded
after the first build on a Docker-enabled host and pinned before any paper-trading deployment.
