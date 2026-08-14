# PROJECT STATUS

**Project:** `ai-trading-lab`

**Repository:** `bdrezek91/Fieldgreen-`

**Updated:** 2026-08-14 UTC

**Mode:** GREENFIELD — independent from every previous trading project

**Allowed modes:** RESEARCH / BACKTEST / PAPER

**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 5 — Benchmark strategies: IMPLEMENTATION COMPLETE**

Work is stopped at the phase boundary. PHASE 6 has not started and requires a new explicit user
instruction.

## DONE

### PHASE 0–4

- Selected an owned modular Python platform, official Bybit V5 boundary, Parquet/DuckDB direction
  and replaceable engine ports.
- Added the fail-closed package, hardened Docker/Compose, CI and documentation.
- Added credential-free public ingestion, exact market-data contracts, immutable Parquet,
  validation, quarantine, lineage/versioning and deterministic resampling.
- Added a conservative deterministic T1 reference backtester with explicit costs, funding, margin,
  next-bar fills, partial fills, OCO ambiguity, approximate liquidation and immutable evidence.
- Added frozen performance metrics, closed-trade reconstruction, manual research verdicts,
  monotonic `EXP-*` allocation and immutable JSON/Parquet/Markdown experiment bundles.

### PHASE 5

- Frozen `benchmark-comparison-policy-v1` before historical market results were inspected.
- Added framework-neutral `BenchmarkSignal` targets `FLAT`, `LONG` and `SHORT`, timestamped at
  closed-candle boundaries.
- Added a separate fixed-quantity comparison policy and compiler; controls cannot set exchange
  fills, costs, leverage or engine behavior.
- Enforced next-bar timing, unique/nonredundant targets, quantity precision, order/notional limits,
  terminal flat exposure and sufficient participation capacity for complete fills.
- Added Buy & Hold, SHA-256-seeded Random Entry, 50-bar prior-window Donchian trend control and
  20-bar rolling z-score mean-reversion control with fixed, non-optimized parameters.
- Added deterministic Random Entry seeds `0..99` and descriptive min/p05/median/mean/p95/max
  net-return distribution. This is not the later 10,000-run Monte Carlo analysis.
- Routed all controls through the same compiler, sizing, execution assumptions, reference engine,
  analytics and optional `ExperimentStore` path.
- Added a network-disabled synthetic suite that records 103 `INCONCLUSIVE` experiments and makes
  no claim of trading edge.
- Added prefix/lookahead, long/short/flat, seeded reproducibility, compiler fairness, distribution,
  evidence persistence and CLI tests.
- Added no candidate strategy family, parameter optimization, walk-forward, regime model, ML,
  credentials, private endpoint, paper adapter or live execution.

## IN PROGRESS

None. Work is intentionally stopped after PHASE 5.

## NEXT

On explicit instruction only: **PHASE 6 — First strategy families**.

Before implementation, freeze one falsifiable economic hypothesis, primary metric, minimum
activity rule, allowed fixed parameters, chronological evaluation windows and exact benchmark
rejection rule. Start with one family and a small predefined real-data matrix. Do not optimize
against synthetic smoke evidence or begin walk-forward, regimes or ML early.

## KNOWN ISSUES

- Docker/Podman is unavailable in the local managed runner. PHASE 5 container validation is pending
  GitHub Actions; PHASE 4 was last proven by run `31774359748`.
- Python and uv images are version-pinned but not content-digest-pinned.
- Public Bybit connectivity still needs proof from GitHub/VPS before historical backfill.
- No curated historical benchmark matrix or historical funding ingestion exists; PHASE 5 therefore
  produces no real-market performance conclusion.
- SQLite is deliberately single-VPS infrastructure and still needs backup/retention/restore policy.
- CAGR and daily risk ratios can be meaningless on very short windows.
- Closed-trade PnL excludes funding allocation; funding remains portfolio-level cash flow.
- Average/Median R and MAE/MFE remain null until point-in-time risk/path contracts exist.
- T1 OHLC lacks real intrabar path, queue position, spread history and depth.
- Margin/liquidation are simplified; leveraged output is not paper-eligible.
- `FixedQuantityPolicy` ensures comparison parity, not risk per trade, volatility targeting or
  portfolio risk; those belong to PHASE 9.
- Administrative final flattening depends on the declared test window and is not an alpha signal.
- Identical evidence may intentionally receive a new experiment ID; hashes expose duplicates.

## RESEARCH QUESTIONS

1. Which single PHASE 6 family and falsifiable economic hypothesis should be tested first?
2. Which predefined BTC/ETH/SOL and 1h/4h UTC windows should form the first real benchmark matrix
   after historical funding is available?
3. Which primary metric and minimum activity threshold should be frozen before PHASE 6 results?
4. Which future risk contract supplies immutable initial risk for valid R-multiple statistics?
5. What backup, retention and restore test should protect market data and research artifacts?
6. When should funding and mark-price ingestion be prioritized relative to PHASE 6?

## PHASE GATE

PHASE 5 local validation at this status update:

- dependency lock and package version `0.5.0`: PASS;
- Ruff lint and format: PASS;
- strict mypy: PASS;
- pytest: 136 PASS;
- statement plus branch coverage: 95.99%, above required 95%;
- all prior data, backtest, analytics and experiment tests: PASS;
- frozen parameters, target contracts and close-prefix lookahead tests: PASS;
- deterministic Random Entry and 100-path distribution tests: PASS;
- flips, flat terminal exposure and compiler fairness rejection tests: PASS;
- synthetic 103-experiment suite: PASS and verdict `INCONCLUSIVE`;
- deterministic backtest, experiment and benchmark CLI smokes: PASS;
- Bandit: PASS;
- dependency audit: PASS;
- source and wheel build: PASS;
- YAML parsing for Compose, CI and pre-commit: PASS;
- LIVE fail-closed tests: PASS;
- local secret-pattern review: PASS;
- Docker Compose and PHASE 5 image build: PENDING GitHub Actions;
- network-disabled benchmark suite on named artifact volume: PENDING GitHub Actions;
- container LIVE fail-closed and Gitleaks: PENDING GitHub Actions;
- credentials or private API fields added: NO (correct);
- candidate alpha strategies added: NO (correct);
- PHASE 6 started: NO (correct).
