# PROJECT STATUS

**Project:** `ai-trading-lab`
**Updated:** 2026-08-14 UTC
**Mode:** GREENFIELD — independent from every previous trading project
**Allowed modes:** RESEARCH / BACKTEST / PAPER
**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 1 — Repository and basic infrastructure: IMPLEMENTATION COMPLETE**

Project execution is paused at the phase boundary. PHASE 2 has not started and must not
start without a new user instruction.

The local environment does not provide a Docker or Podman runtime. Compose and workflow YAML
were parsed successfully, while the actual image build and Compose runtime checks remain
mandatory in GitHub Actions or on the target VPS.

## DONE

### PHASE 0

- Researched the 2026 technology landscape.
- Compared Freqtrade, NautilusTrader, VectorBT/Pro, Backtrader, custom Python, CCXT/Pro,
  official Bybit V5 and time-series ML tooling.
- Selected an owned modular research platform with replaceable framework adapters.
- Designed data, backtest, experiment, validation, regime, risk, portfolio, execution, ML,
  VPS and security layers.

### PHASE 1

- Created a new local Git repository on branch `main`.
- Added a Python 3.12 package with a reproducible `uv.lock`.
- Added a minimal CLI and safe infrastructure heartbeat.
- Added fail-closed settings supporting only `RESEARCH`, `BACKTEST` and `PAPER`.
- Explicitly blocked `LIVE` for case and whitespace variants.
- Added a safe `.env.example` with no exchange or secret fields.
- Added `.gitignore` rules for secrets, market data, artifacts, models, databases and logs.
- Added a non-root, read-only Docker image definition.
- Added a Compose service with:
  - no network;
  - no exposed ports;
  - all capabilities dropped;
  - `no-new-privileges`;
  - read-only root filesystem;
  - bounded temporary storage;
  - healthcheck and restart policy.
- Added GitHub Actions jobs for:
  - Ruff lint and format;
  - strict mypy;
  - pytest with coverage;
  - Bandit;
  - dependency audit;
  - Gitleaks;
  - Compose validation and Docker build;
  - proof that a container configured as `LIVE` fails.
- Added pre-commit configuration for Ruff and Gitleaks.
- Added baseline documentation:
  - `README.md`;
  - `docs/ARCHITECTURE.md`;
  - `docs/RESEARCH_METHODOLOGY.md`;
  - `docs/DATA.md`;
  - `docs/BACKTESTING.md`;
  - `docs/ML.md`;
  - `docs/VPS_DEPLOYMENT.md`.
- Resolved a dependency-audit finding by upgrading pytest from the vulnerable 8.4 line to a
  fixed 9.x release.

## IN PROGRESS

None. Work is intentionally stopped after PHASE 1.

## NEXT

On explicit instruction only: **PHASE 2 — Data engine**.

Proposed PHASE 2 scope:

- define stable market-data and instrument contracts;
- implement an official Bybit V5 public-data adapter without credentials;
- ingest instrument metadata and closed OHLCV candles;
- implement raw, normalized, curated and quarantine zones;
- store versioned Parquet datasets on a local/VPS volume;
- validate UTC, schema, duplicates, gaps, continuity, OHLC invariants, zero volume, anomalies
  and incomplete candles;
- create dataset manifests with hashes and transformation lineage;
- add deterministic 1m-to-higher-timeframe resampling and parity checks;
- add data-integrity, contract and idempotency tests;
- keep execution, strategies, API keys and LIVE out of scope.

## KNOWN ISSUES

- Docker/Podman is unavailable in the current execution environment, so the actual image build,
  healthcheck and Compose lifecycle were not run locally. CI contains these checks and must pass
  before a release or VPS deployment.
- The Docker base image is pinned to the exact `3.12.14-slim-bookworm` tag but not yet to a full
  content digest. Record and pin the amd64 digest on the first Docker-enabled build.
- GitHub remote repository and branch protection are not configured yet; the local repository is
  ready to publish after the repository owner/visibility is selected.
- NautilusTrader is not installed; its version remains intentionally deferred to the PHASE 3
  capability gate.
- No dataset, PostgreSQL service or experiment registry exists yet; those belong to later phases.

## RESEARCH QUESTIONS

1. Which GitHub owner and repository visibility should be used when publishing the local repo?
2. What retention period and disk budget should PHASE 2 use for raw Bybit responses?
3. Should initial historical ingestion start only from 1m and derive higher timeframes, while
   storing native Bybit higher-timeframe data solely for parity checks?
4. What initial historical date should be requested for symbols listed at different times?
5. Which full Docker base-image digest is observed on the target linux/amd64 build host?
6. Which stable Nautilus v2 release should enter the PHASE 3 capability gate?

## PHASE GATE

PHASE 1 validation:

- Python dependency lock: PASS;
- Ruff lint: PASS;
- Ruff format: PASS;
- strict mypy: PASS;
- pytest: 24 PASS;
- statement and branch coverage: 100%;
- Bandit: PASS;
- dependency audit: PASS, no known vulnerabilities;
- safe CLI status: PASS;
- LIVE fail-closed runtime check: PASS;
- YAML parsing (Compose, CI, pre-commit): PASS;
- `.gitignore` review: PASS;
- local secret-pattern review: PASS;
- documentation review: PASS;
- Docker build/Compose lifecycle: NOT RUN — runtime unavailable; mandatory CI check present;
- strategies created: NO (correct);
- API keys configured: NO (correct);
- market data downloaded: NO (correct);
- PHASE 2 started: NO (correct).
