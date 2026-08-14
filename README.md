# AI Trading Lab

Greenfield, research-first platform for testing whether a systematic trading edge exists.

The project has completed **PHASE 6 — First Strategy Family**. It contains the PHASE 2
credential-free Bybit data engine, the PHASE 3 deterministic T1 reference backtester, frozen
performance metrics, monotonic `EXP-*` evidence, four frozen comparison controls and one
pre-registered dual-channel trend candidate. It has no validated edge, exchange credentials,
paper adapter or live execution path.

## Safety boundary

Allowed modes:

- `RESEARCH`
- `BACKTEST`
- `PAPER`

`LIVE` is intentionally absent from the mode enum. Any attempt to configure it fails closed.
The long-running research service also has networking disabled. Network access is available only
to the explicit one-shot public-data service.

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
uv run atl backtest self-test
uv run atl experiment self-test
uv run atl benchmark self-test
uv run atl strategy self-test
```

Public data examples:

```bash
ATL_DATA_ROOT=data uv run atl data instruments
ATL_DATA_ROOT=data uv run atl data candles \
  --symbol BTCUSDT --timeframe 1m \
  --start 2026-08-01T00:00:00Z --end 2026-08-02T00:00:00Z
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

The default container is a research heartbeat, not a trader. It exposes no ports and cannot reach
the network. Public ingestion is run explicitly and writes only to the `market-data` volume:

```bash
docker compose --profile data run --rm data \
  python -m ai_trading_lab data instruments
```

## Project boundaries

The architecture decision and research are documented in
[`docs/PHASE_0_ARCHITECTURE_RESEARCH.md`](docs/PHASE_0_ARCHITECTURE_RESEARCH.md).
Current progress is tracked in [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

Market datasets, experiment artifacts, models, databases, logs and local configuration are
excluded from Git. No prior trading project, strategy or integration is reused.

The data contract, layout and integrity gates are documented in
[`docs/DATA.md`](docs/DATA.md).

The exact execution model and limitations are documented in
[`docs/BACKTESTING.md`](docs/BACKTESTING.md). The 2026 NautilusTrader capability decision is in
[`docs/PHASE_3_NAUTILUS_CAPABILITY_GATE.md`](docs/PHASE_3_NAUTILUS_CAPABILITY_GATE.md).

Metric definitions, verdict rules and experiment artifacts are documented in
[`docs/ANALYTICS.md`](docs/ANALYTICS.md).

Frozen PHASE 5 controls, parameters and pre-result comparison rules are documented in
[`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

The first falsifiable strategy-family protocol, sealed chronology and rejection gate are in
[`docs/STRATEGY_FAMILY_1.md`](docs/STRATEGY_FAMILY_1.md).
