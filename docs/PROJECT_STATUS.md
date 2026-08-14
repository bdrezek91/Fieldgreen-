# PROJECT STATUS

**Project:** `ai-trading-lab`

**Repository:** `bdrezek91/Fieldgreen-`

**Updated:** 2026-08-14 UTC

**Mode:** GREENFIELD — independent from every previous trading project

**Allowed modes:** RESEARCH / BACKTEST / PAPER

**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 6 — First strategy family: IMPLEMENTATION COMPLETE**

Work is stopped at the phase boundary. PHASE 7 has not started and requires a new explicit user
instruction. PHASE 6 produced a reproducible research protocol and candidate implementation, not
evidence of a trading edge.

## DONE

### PHASE 0–5

- Selected a modular owned platform, official Bybit V5 data boundary and replaceable engine ports.
- Added hardened Docker/Compose, CI, credential-free public ingestion, immutable validated
  Parquet/lineage and deterministic resampling.
- Added a conservative deterministic T1 bar backtester with explicit execution costs, funding,
  margin, next-bar fills, OCO ambiguity and approximate liquidation.
- Added versioned analytics, monotonic `EXP-*` evidence and immutable experiment bundles.
- Added Buy & Hold, 100-seed Random Entry, Simple Trend Following and Simple Mean Reversion under
  one frozen comparison policy.

### PHASE 6

- Registered exactly one falsifiable hypothesis: `HYP-TREND-DUAL-CHANNEL-001`.
- Frozen one symmetric dual-channel candidate with 55-bar entry and 20-bar exit lookbacks; no
  parameter optimization or historical result inspection was performed.
- Frozen TRAIN 2022–2023, VALIDATION 2024 and sealed TEST 2025 half-open UTC windows.
- Frozen the six-cell BTCUSDT/ETHUSDT/SOLUSDT × 1h/4h validation matrix, median net return primary
  metric, 60-trade activity floor and four-of-six comparison rules.
- Required complete curated Bybit data and historical funding for real evidence. Synthetic or
  incomplete evidence deterministically returns `INCONCLUSIVE`.
- Added deterministic outcomes `ADVANCE_TO_PHASE_7`, `REJECTED` and `INCONCLUSIVE`; advancement is
  explicitly not proof of edge.
- Promoted the reusable signal contract/compiler out of the benchmark package while retaining
  compatibility aliases for existing controls.
- Routed candidate and controls through identical fixed sizing, next-bar execution, analytics and
  immutable experiment storage.
- Added a network-disabled synthetic smoke that records 104 experiments, keeps TEST sealed and
  returns `INCONCLUSIVE`.
- Added protocol, validation-gate, prefix/lookahead, symmetric-direction, persistence and CLI
  tests. Added no regimes, walk-forward, ML, credentials, private API or execution adapter.

## IN PROGRESS

None. Work is intentionally stopped after PHASE 6.

## NEXT

On explicit instruction only: **PHASE 7 — Walk-forward and robustness**.

Before opening the sealed TEST window, first complete historical funding ingestion and the exact
curated validation matrix. Run the frozen PHASE 6 gate once and record every result. Only an
`ADVANCE_TO_PHASE_7` decision permits robustness work; `REJECTED` ends the family and
`INCONCLUSIVE` requires resolving the stated evidence deficiency without retuning the strategy.

## KNOWN ISSUES

- Docker/Podman is unavailable in the local managed runner; GitHub Actions is the container gate.
- Python and uv images are version-pinned but not content-digest-pinned.
- No historical funding ingestion or complete curated six-cell validation matrix exists; the
  family therefore has no real-market decision.
- Public Bybit connectivity still needs an operational VPS backfill proof.
- SQLite is single-VPS infrastructure and needs backup/retention/restore policy.
- Funding remains portfolio-level cash flow rather than allocated closed-trade PnL.
- Average/Median R and MAE/MFE remain null until point-in-time risk/path contracts exist.
- T1 OHLC lacks true intrabar path, queue position, historical spread and depth.
- Margin/liquidation are simplified and leveraged output is not paper-eligible.
- Fixed quantity is a comparison control, not PHASE 9 portfolio risk management.
- Administrative terminal flattening depends on the declared window and is not alpha.

## RESEARCH QUESTIONS

1. Can official Bybit sources provide complete, versioned funding and mark-price history for all
   six validation cells and frozen windows?
2. Does the single registered family pass its frozen VALIDATION gate without any parameter change?
3. If advanced, how should PHASE 7 implement rolling windows, bootstrap, PBO/Deflated Sharpe and
   the 10,000-run Monte Carlo while preserving the attempt ledger?
4. What backup and restore test should protect market data and experiment evidence on the VPS?
5. Which immutable risk contract later supplies valid initial R and portfolio constraints?

## PHASE GATE

PHASE 6 local validation at this status update:

- package version `0.6.0`, frozen dependency sync and lock: PASS;
- Ruff lint/format and strict mypy across 40 source files: PASS;
- pytest: 146 PASS; statement plus branch coverage: 95.81%, above required 95%;
- Bandit, dependency audit, source/wheel build and YAML parsing: PASS;
- signal contract/compiler regression and strategy prefix-invariance tests: PASS during development;
- synthetic 104-experiment integration: PASS, decision `INCONCLUSIVE`, TEST `SEALED`;
- LIVE fail-closed and local secret-pattern review: PASS;
- Docker Compose/image/runtime and Gitleaks: pending GitHub Actions validation;
- credentials, private API fields, paper/live execution added: NO (correct);
- real-market edge claimed: NO (correct);
- PHASE 7 started: NO (correct).
