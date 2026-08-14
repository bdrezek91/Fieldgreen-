# PROJECT STATUS

**Project:** `ai-trading-lab`

**Repository:** `bdrezek91/Fieldgreen-`

**Updated:** 2026-08-14 UTC

**Mode:** GREENFIELD — independent from every previous trading project

**Allowed modes:** RESEARCH / BACKTEST / PAPER

**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 3 — Backtesting engine: IMPLEMENTATION COMPLETE**

Work is stopped at the phase boundary. PHASE 4 has not started and requires a new explicit user
instruction.

## DONE

### PHASE 0

- Researched the 2026 technology landscape and selected an owned modular Python platform.
- Chose official Bybit V5 as the initial data source, Parquet/DuckDB for analytics and replaceable
  engine adapters behind project-owned contracts.

### PHASE 1

- Created the package, dependency lock, fail-closed settings, hardened Docker/Compose baseline,
  CI, tests and core documentation.
- Published the greenfield repository to `bdrezek91/Fieldgreen-`.

### PHASE 2

- Implemented credential-free official Bybit V5 public ingestion, strict domain contracts,
  UTC/exact-decimal normalization, raw evidence, immutable Parquet zones, quarantine, integrity
  reports, dataset lineage/versioning and deterministic resampling.
- Added the initial 11-symbol universe and six required timeframes without adding API keys.

### PHASE 3

- Re-checked the official NautilusTrader release state and documentation on 2026-08-14.
- Ran an isolated `2.0.0rc2` capability spike without adding it to production dependencies.
- Deferred Nautilus adoption because stable v2 was unavailable and native bar callbacks do not
  guarantee the required next-bar-open execution rule.
- Added owned, framework-neutral contracts for order intents, assumptions, funding/mark events,
  fills, ledger events, positions, equity and canonical results.
- Added a deterministic T1 bar-event reference kernel supporting long/short, position flips,
  market/limit/stop-market, GTC/IOC, reduce-only, OCO, partial fills, latency and multi-symbol order.
- Added explicit maker/taker fees, spread, slippage, tick/quantity precision, minimum notional,
  leverage/margin checks, funding and an intentionally approximate liquidation model.
- Enforced close-to-next-open execution and conservative same-bar stop/target resolution.
- Added immutable canonical JSON backtest artifacts with overwrite protection.
- Added a deterministic synthetic `atl backtest self-test` and container parity check.
- Added capability-gate, architecture, backtesting, VPS and README documentation.
- Added no strategy, feature, alpha optimization, ML, private exchange or execution adapter.

## IN PROGRESS

None. Work is intentionally stopped after PHASE 3.

## NEXT

On explicit instruction only: **PHASE 4 — Analytics and experiment tracking**.

Proposed PHASE 4 scope:

- allocate monotonic `EXP-000001` experiment IDs safely;
- persist the complete reproducibility envelope: Git commit, dataset/engine/assumptions versions,
  date range, symbols, timeframes, parameters and timestamps;
- derive trade records and the required performance/risk/cost metrics from the canonical ledger;
- create machine-readable JSON/Parquet evidence and a human-readable report;
- distinguish `REJECTED`, `INCONCLUSIVE` and passed research outcomes;
- keep benchmark strategies, parameter search, Monte Carlo and walk-forward out until their
  assigned phases.

## KNOWN ISSUES

- Docker/Podman is unavailable in the local managed runner. GitHub Actions run `31772317596`
  successfully validated the Compose config, PHASE 3 image and runtime behavior.
- The Python and uv image references are version-pinned but not content-digest-pinned.
- Public Bybit connectivity was blocked by the managed runner gateway in PHASE 2 and remains to be
  proven from GitHub/VPS before backfill.
- The T1 OHLC kernel cannot know the real intrabar path, spread history, queue position or depth.
- Bar participation is a deterministic cap, not a probabilistic fill or market-impact model.
- Funding and mark contracts exist, but their historical ingestion is not implemented.
- Margin and liquidation are simplified. Any leveraged result is not paper-eligible.
- Bybit risk tiers, cross margin, bankruptcy price and insurance-fund mechanics are not modeled.
- T0 vectorized screening, stable Nautilus adapter and T2 trade/order-book replay are deferred.
- Experiment indexing and analytical performance metrics do not exist until PHASE 4.
- Raw retention, backup, disk budget and incremental data scheduling remain undecided.

## RESEARCH QUESTIONS

1. Which future stable NautilusTrader v2 release can pass golden parity against the reference
   kernel and preserve explicit next-bar scheduling?
2. Which historical Bybit risk-tier snapshots are obtainable for exact liquidation research?
3. What bar-participation and slippage assumptions are defensible before trade-level calibration?
4. Should experiment state begin with SQLite on a single VPS while bulk evidence stays Parquet?
5. What raw-response retention period, experiment retention policy and disk budget fit the VPS?
6. Which metric definitions and annualization rules should be frozen before benchmark comparisons?

## PHASE GATE

PHASE 3 validation at the time of this status update:

- dependency lock and package version `0.3.0`: PASS;
- Ruff lint and format: PASS;
- strict mypy: PASS;
- pytest: 105 PASS;
- statement and branch coverage: above required 95%;
- no-same-close and future-prefix invariance tests: PASS;
- fee, funding-sign, spread/slippage and precision tests: PASS;
- long/short, flips, reduce-only and margin tests: PASS;
- partial-fill, IOC/GTC and latency tests: PASS;
- conservative same-bar OCO test: PASS;
- approximate long/short liquidation tests: PASS;
- deterministic multi-symbol and repeated-run tests: PASS;
- immutable artifact and overwrite-protection tests: PASS;
- deterministic CLI smoke repeated locally: PASS;
- Bandit: PASS;
- dependency audit: PASS;
- YAML parsing for Compose, CI and pre-commit: PASS;
- LIVE fail-closed tests: PASS;
- Docker Compose config and PHASE 3 image build: PASS in GitHub Actions run `31772317596`;
- network-disabled container self-test equality: PASS in GitHub Actions run `31772317596`;
- Gitleaks: PASS in GitHub Actions run `31772317596`;
- local secret-pattern review: PASS;
- credentials or private API fields added: NO (correct);
- strategies, features, ML or paper/live execution added: NO (correct);
- PHASE 4 started: NO (correct).
