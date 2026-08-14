# PROJECT STATUS

**Project:** `ai-trading-lab`

**Repository:** `bdrezek91/Fieldgreen-`

**Updated:** 2026-08-14 UTC

**Mode:** GREENFIELD — independent from every previous trading project

**Allowed modes:** RESEARCH / BACKTEST / PAPER

**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 4 — Analytics and experiment tracking: IMPLEMENTATION COMPLETE**

Work is stopped at the phase boundary. PHASE 5 has not started and requires a new explicit user
instruction.

## DONE

### PHASE 0

- Researched the 2026 technology landscape and selected an owned modular Python platform.
- Chose official Bybit V5, Parquet/DuckDB direction and replaceable engines behind owned ports.

### PHASE 1

- Created the package, lock, fail-closed settings, hardened Docker/Compose, CI and documentation.

### PHASE 2

- Implemented credential-free Bybit V5 public ingestion, exact data contracts, immutable Parquet,
  integrity validation, quarantine, lineage/versioning and deterministic resampling.

### PHASE 3

- Deferred NautilusTrader until stable v2 and explicit next-bar scheduling pass a future gate.
- Implemented owned backtest contracts and a conservative deterministic T1 reference kernel.
- Added realistic explicit costs, funding, margin, partial fills, OCO ambiguity policy, approximate
  liquidation, canonical ledger/equity and immutable backtest JSON.

### PHASE 4

- Added framework-neutral `TradeRecord`, `PerformanceMetrics` and `AnalyticsResult` contracts.
- Reconstructed closed long/short trades from fills, including partial exits, fee allocation and
  position flips.
- Frozen `performance-metrics-v1` definitions for returns, CAGR, win/loss statistics, expectancy,
  profit factor, Sharpe, Sortino, Calmar, drawdown, Ulcer, exposure, turnover, fees and funding.
- Kept Average/Median R, MAE and MFE explicitly null and listed as unavailable until future
  point-in-time risk and path contracts make them valid.
- Added manual `PASSED`, `REJECTED` and `INCONCLUSIVE` verdicts with mandatory reasons; profit does
  not assign a verdict automatically.
- Added a transactional SQLite lifecycle registry using `AUTOINCREMENT` and `BEGIN IMMEDIATE`.
- Added monotonic `EXP-000001` IDs that remain consumed after a failed artifact publication.
- Added immutable experiment bundles with manifest JSON, exact metrics JSON, trades Parquet,
  human-readable Markdown and SHA-256 lineage to canonical backtest evidence.
- Captured Git commit, dataset/date/universe/timeframes, strategy version, parameters, complete
  execution/funding/mark assumptions, engine/metric versions and UTC timestamps.
- Added a network-disabled experiment self-test and a dedicated VPS artifact volume.
- Added no benchmark strategy, alpha search, optimization, Monte Carlo, walk-forward, ML, API keys,
  private exchange endpoint, paper adapter or live execution.

## IN PROGRESS

None. Work is intentionally stopped after PHASE 4.

## NEXT

On explicit instruction only: **PHASE 5 — Benchmark strategies**.

Proposed PHASE 5 scope:

- freeze one shared signal and risk interface before implementing benchmarks;
- implement Buy & Hold, seeded Random Entry, Simple Trend Following and Simple Mean Reversion;
- use identical sizing, costs, exit opportunity and experiment evidence wherever comparison permits;
- run benchmarks across declared symbol/timeframe/date windows without parameter optimization;
- repeat Random Entry across many deterministic seeds and report its distribution, not one path;
- define pre-run benchmark acceptance/comparison rules;
- record every run through `ExperimentStore` and reject unsupported conclusions;
- do not begin PHASE 6 strategy-family research.

## KNOWN ISSUES

- Docker/Podman is unavailable in the local managed runner; final PHASE 4 image and volume behavior
  require GitHub Actions validation after publication.
- Python and uv image references are version-pinned but not content-digest-pinned.
- Public Bybit connectivity still requires proof from GitHub/VPS before historical backfill.
- SQLite is intentionally single-VPS infrastructure; multi-host workers will require PostgreSQL.
- SQLite and Parquet evidence need a VPS backup/retention policy before long-running research.
- CAGR and daily risk ratios can be mathematically valid but meaningless on very short windows.
- Closed-trade PnL excludes funding allocation; funding remains a portfolio-level cash flow.
- Average/Median R, MAE and MFE are null because initial planned risk and trade paths are absent.
- Funding and mark contracts exist, but their historical ingestion is not implemented.
- T1 OHLC still lacks the real intrabar path, queue position, spread history and market depth.
- Margin/liquidation remain simplified; leveraged results are not paper-eligible.
- No experiment deduplication policy prevents intentionally rerunning identical evidence under a
  new `EXP-*` ID; the request and artifact hashes make duplicates detectable.

## RESEARCH QUESTIONS

1. What exact signal contract lets Random Entry and deterministic benchmarks share exit/risk rules?
2. How many Random Entry seeds are sufficient for the first benchmark distribution before the
   later 10,000-run Monte Carlo requirement?
3. Which fixed, non-optimized parameters are defensible for the simple trend and mean-reversion
   controls?
4. Should benchmark evidence begin on BTCUSDT 1h before expanding to all 11 symbols and six
   timeframes, or use a small predefined matrix immediately?
5. Which future risk contract supplies immutable initial risk for valid R-multiple statistics?
6. What backup, retention and restore test should protect `market-data` and `research-artifacts`?

## PHASE GATE

PHASE 4 validation at the time of this status update:

- dependency lock and package version `0.4.0`: PASS;
- Ruff lint and format: PASS;
- strict mypy: PASS;
- pytest: 122 PASS;
- statement and branch coverage: 95.45%, above required 95%;
- long/short, partial-close, fee-allocation and position-flip reconstruction tests: PASS;
- metric sign, drawdown, exposure, turnover, funding and null-availability tests: PASS;
- monotonic concurrent `EXP-*` allocation test: PASS;
- failed-publication lifecycle and non-reuse test: PASS;
- manifest, exact JSON, Parquet schema, Markdown and hash-lineage tests: PASS;
- deterministic backtest and experiment CLI smoke tests: PASS;
- Bandit: PASS;
- dependency audit: PASS;
- YAML parsing for Compose, CI and pre-commit: PASS;
- LIVE fail-closed tests: PASS;
- local secret-pattern review: PASS;
- Docker Compose, PHASE 4 image, artifact-volume permissions and Gitleaks: pending GitHub Actions;
- credentials or private API fields added: NO (correct);
- benchmark or alpha strategies added: NO (correct);
- PHASE 5 started: NO (correct).
