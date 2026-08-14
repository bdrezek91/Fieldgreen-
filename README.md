# AI Trading Lab

Greenfield, research-first platform for testing whether a systematic trading edge exists.

The project currently contains **PHASE 1 infrastructure only**. It has no strategies, no
market-data client, no exchange credentials and no live execution path.

## Safety boundary

Allowed modes:

- `RESEARCH`
- `BACKTEST`
- `PAPER`

`LIVE` is intentionally absent from the mode enum. Any attempt to configure it fails closed.
The PHASE 1 Compose service also has networking disabled.

## Requirements

- Linux or macOS development environment;
- Python 3.12;
- [uv](https://docs.astral.sh/uv/);
- Docker with the Compose plugin for container validation.

## Local setup

```bash
uv sync --frozen
uv run atl status
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run bandit -q -r src
uv run pip-audit
```

## Docker

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --no-color research
docker compose down
```

The current container is an infrastructure heartbeat, not a trader. It exposes no ports and
cannot reach the network.

## Project boundaries

The architecture decision and research are documented in
[`docs/PHASE_0_ARCHITECTURE_RESEARCH.md`](docs/PHASE_0_ARCHITECTURE_RESEARCH.md).
Current progress is tracked in [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

Market datasets, experiment artifacts, models, databases, logs and local configuration are
excluded from Git. No prior trading project, strategy or integration is reused.
