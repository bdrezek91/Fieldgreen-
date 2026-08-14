# VPS Deployment

Status: PHASE 3 data and offline-backtest baseline.

Target: Linux VPS with Git, Docker Engine and the Docker Compose plugin.

```bash
git clone https://github.com/bdrezek91/Fieldgreen-.git
cd Fieldgreen-
cp .env.example .env
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

The default `research` service exposes no port, runs as an unprivileged user, has all Linux
capabilities dropped, uses a read-only filesystem and has networking disabled. It is a safe
infrastructure heartbeat only. PHASE 2 adds an opt-in, one-shot public-data service. Market data
lives in the named `market-data` volume.

Create the initial public instrument snapshot:

```bash
docker compose --profile data run --rm data \
  python -m ai_trading_lab data instruments
```

Ingest one closed UTC candle window:

```bash
docker compose --profile data run --rm data \
  python -m ai_trading_lab data candles \
  --symbol BTCUSDT --timeframe 1m \
  --start 2026-08-01T00:00:00Z --end 2026-08-02T00:00:00Z
```

The `data` service uses only official public Bybit V5 market endpoints. Do not add API keys to its
environment. Scheduled incremental collection and backup policy are deferred.

The base image is version-pinned to Python 3.12.14 slim-bookworm. A digest must be recorded
after the first build on a Docker-enabled host and pinned before any paper-trading deployment.

Verify the offline engine twice; both JSON documents must be identical:

```bash
docker run --rm --network none ai-trading-lab:phase-3 \
  python -m ai_trading_lab backtest self-test
docker run --rm --network none ai-trading-lab:phase-3 \
  python -m ai_trading_lab backtest self-test
```

Real backtest artifacts will be stored on a dedicated experiment volume in PHASE 4. Do not write
them into the cloned repository. There is still no exchange execution process, private endpoint or
API-key configuration in this phase.
