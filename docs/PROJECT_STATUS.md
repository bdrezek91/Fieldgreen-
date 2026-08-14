# PROJECT STATUS

**Project:** `ai-trading-lab`
**Repository:** `bdrezek91/Fieldgreen-`
**Updated:** 2026-08-14 UTC
**Mode:** GREENFIELD — independent from every previous trading project
**Allowed modes:** RESEARCH / BACKTEST / PAPER
**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 2 — Data engine: IMPLEMENTATION COMPLETE**

Work is stopped at the phase boundary. PHASE 3 has not started and requires a new explicit user
instruction.

## DONE

### PHASE 0

- Researched the 2026 technology landscape and selected an owned modular Python platform.
- Chose official Bybit V5 as the initial source of truth, Parquet/DuckDB for analytical data and
  replaceable NautilusTrader/VectorBT adapters at later capability gates.

### PHASE 1

- Created the package, dependency lock, fail-closed settings, hardened Docker/Compose baseline,
  CI, tests and core documentation.
- Published the project to `bdrezek91/Fieldgreen-`; the first remote CI run passed.

### PHASE 2

- Verified current official Bybit V5 kline, instrument, server-time and rate-limit contracts.
- Added provider-independent `Candle`, `Instrument` and `Timeframe` contracts.
- Added the required initial 11-symbol universe and six timeframes.
- Implemented a credential-free official Bybit V5 adapter with strict parsing, instrument cursor
  pagination, backward kline pagination, identity checks, universe-completeness checks, bounded
  HTTPS retries, a pre-normalization raw-page sink and server-time-based incomplete-candle removal.
- Implemented immutable raw, normalized, curated and quarantine zones.
- Added canonical gzip JSON evidence and Parquet/Zstandard analytical storage.
- Added UTC millisecond timestamps and exact `decimal128(38,18)` numeric storage.
- Added Hive-style partitioning by timeframe, symbol, year and month.
- Added atomic writes, SHA-256 hashes, content-derived `DS-*` versions and lineage manifests.
- Added validation for empty data, mixed series, UTC, alignment, duplicates, ordering, gaps,
  continuity, incomplete candles, OHLC, negative activity, zero volume and price anomalies.
- Added deterministic complete-bucket resampling and field-level native parity checks.
- Added safe CLI commands and a dedicated one-shot Compose data service with persistent volume.
- Updated README, architecture, data, backtesting and VPS documentation.

## IN PROGRESS

None. Work is intentionally stopped after PHASE 2.

## NEXT

On explicit instruction only: **PHASE 3 — Backtesting engine capability gate and implementation**.

Proposed PHASE 3 scope:

- freeze execution semantics and event ordering before adding strategies;
- run a NautilusTrader version/capability spike against owned data contracts;
- verify fees, spread, slippage, leverage, funding, stops, liquidation approximations and
  multi-asset portfolio behavior;
- define order, fill, position and portfolio contracts independent of NautilusTrader;
- implement deterministic backtest configuration and result artifacts;
- add lookahead, same-bar ambiguity and close-fill prohibition tests;
- do not create alpha strategies yet.

## KNOWN ISSUES

- Docker/Podman is unavailable in the current local execution environment. GitHub Actions run
  `31770857885` successfully validated Compose, the PHASE 2 image build, PyArrow import inside the
  image and the container-level LIVE block.
- The Python and uv image references are version-pinned but not content-digest-pinned.
- A public API smoke test from the local managed runner was blocked by its network gateway, which
  returned a non-JSON response. Mocked official-contract tests pass; connectivity must be proven by
  an explicit public-data command on GitHub/VPS before historical backfill.
- No raw-data retention, backup or disk-budget policy is selected for the VPS.
- Incremental scheduling, late-arriving data reconciliation and recovery checkpoints are not yet
  implemented.
- Funding, open interest, mark/index prices, trades, liquidations and order books are designed as
  extensions but are not ingested in PHASE 2.
- The engine intentionally does not auto-fill missing candles. Gapped batches are quarantined.
- DuckDB is selected architecturally but is not needed or installed until a query/catalog consumer
  is implemented.

## RESEARCH QUESTIONS

1. What raw-response retention period and disk budget should be used on the VPS?
2. What is the earliest desired history, per instrument launch date?
3. Should canonical higher timeframes be derived only from native 1m, with native HTF retained
   solely for parity checks?
4. What parity tolerances should be allowed for volume and turnover after provider corrections?
5. Should incremental ingestion run every minute, every five minutes, or by WebSocket plus REST
   reconciliation in a later operations phase?
6. Which stable NautilusTrader v2 release passes the PHASE 3 capability gate?

## PHASE GATE

PHASE 2 validation at the time of this status update:

- dependency lock with PyArrow 23.0.1: PASS;
- Ruff lint and format: PASS;
- strict mypy: PASS;
- pytest: 60 PASS;
- statement and branch coverage: 95.59%;
- required data-integrity tests: PASS;
- adapter contract and pagination tests: PASS;
- storage, manifest, quarantine and idempotency tests: PASS;
- resampling and parity tests: PASS;
- Bandit: PASS;
- dependency audit: PASS, no known vulnerabilities after replacing vulnerable PyArrow 21.0.0;
- YAML parsing for Compose, CI and pre-commit: PASS;
- LIVE fail-closed tests: PASS;
- Docker Compose config and PHASE 2 image build: PASS in GitHub Actions;
- container runtime dependency import: PASS in GitHub Actions;
- Gitleaks: PASS in GitHub Actions;
- local secret-pattern review: PASS;
- public Bybit smoke test: NOT RUN TO COMPLETION — managed network gateway returned non-JSON;
- local Docker build/Compose lifecycle: NOT RUN — runtime unavailable; remote CI equivalent PASS;
- credentials or private API fields added: NO (correct);
- strategies/backtester/execution added: NO (correct);
- PHASE 3 started: NO (correct).
