# PROJECT STATUS

**Project:** `ai-trading-lab`

**Repository:** `bdrezek91/Fieldgreen-`

**Updated:** 2026-08-14 UTC

**Mode:** GREENFIELD — independent from every previous trading project

**Allowed modes:** RESEARCH / BACKTEST / PAPER

**LIVE:** HARD-BLOCKED; out of scope until PHASE 15

## CURRENT PHASE

**PHASE 6 — Real-evidence gate readiness: IMPLEMENTATION COMPLETE; DATA BLOCKED**

PHASE 7 was authorized conditionally, but its entry gate cannot run without the curated 2024 Bybit
matrix. PHASE 7 robustness work has therefore not started. PHASE 6 still provides no evidence of a
trading edge.

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
- Added official public funding-history and mark-price-kline adapters with backward pagination,
  immutable raw evidence, exact decimals, Parquet partitioning and manifests.
- Added funding cadence/boundary validation and OHLCV/mark requested-window boundary checks;
  partial, duplicate, missing or misaligned history is quarantined.
- Added hash-verifying curated-data loaders and exact manifest selection; missing, ambiguous or
  corrupt inputs fail closed.
- Added the one-shot six-cell VALIDATION runner: 624 experiments, fixed quantities/cash, complete
  funding and mark-price inputs, immutable gate artifact and no TEST selection path.

## IN PROGRESS

Real backfill is blocked by public Bybit connectivity in the managed runner. The attempted official
`api.bybit.com/v5/market/time` request returned `Site Unavailable`; no substitute data was used.

## NEXT

On a network-enabled VPS: backfill and curate the exact 2024 matrix, then run the frozen gate once.

Before opening the sealed TEST window, first complete historical funding ingestion and the exact
curated validation matrix. Run the frozen PHASE 6 gate once and record every result. Only an
`ADVANCE_TO_PHASE_7` decision permits robustness work; `REJECTED` ends the family and
`INCONCLUSIVE` requires resolving the stated evidence deficiency without retuning the strategy.

## KNOWN ISSUES

- Docker/Podman is unavailable in the local managed runner; GitHub Actions is the container gate.
- Python and uv images are version-pinned but not content-digest-pinned.
- Historical ingestion code exists, but the complete curated six-cell matrix is not present; the
  family therefore has no real-market decision.
- Public Bybit access is blocked in the managed runner and needs an operational VPS backfill.
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

PHASE 6 gate-readiness validation at this status update:

- package version `0.6.1`, frozen dependency sync and lock consistency: PASS;
- Ruff lint/format and strict mypy across 42 source files: PASS;
- pytest: 162 PASS; statement plus branch coverage: 95.06%, above required 95%;
- Bandit: PASS; dependency audit: no known vulnerabilities in auditable dependencies;
- source distribution, wheel build and YAML parsing: PASS;
- signal contract/compiler regression and strategy prefix-invariance tests: PASS during development;
- synthetic 104-experiment integration: PASS, decision `INCONCLUSIVE`, TEST `SEALED`;
- LIVE fail-closed and local secret-pattern review: PASS;
- local missing-matrix fail-closed test: PASS with exit code 3, `INCONCLUSIVE` and TEST `SEALED`;
- local Docker is unavailable; Compose, image and Gitleaks remain pending GitHub Actions;
- credentials, private API fields, paper/live execution added: NO (correct);
- real-market edge claimed: NO (correct);
- real Bybit backfill completed: NO — network blocker recorded, no fabrication;
- PHASE 7 robustness started: NO (correct; entry gate not passed).
