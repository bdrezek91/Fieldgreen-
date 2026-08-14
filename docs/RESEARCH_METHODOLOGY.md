# Research Methodology

Status: PHASE 6 first strategy-family protocol implemented; real validation remains blocked.

Research must be hypothesis-led, reproducible and falsifiable. Optimization data and evaluation
data remain separate. Final evidence will be chronological out-of-sample performance after
realistic costs and comparison with benchmarks including Random Entry under equivalent risk.

## Rules already enforced

- immutable dataset, backtest, assumptions and metric versions;
- Git commit and parameter capture;
- deterministic execution and next-bar-open prohibition;
- exact UTC date range, universe and timeframe capture;
- explicit `PASSED`, `REJECTED` or `INCONCLUSIVE` verdict with reason;
- missing metrics remain null rather than estimated after observing outcomes;
- failed evidence publication is audited and experiment IDs are never reused;
- generated datasets, databases, reports and experiments stay outside Git.

## Advancement rule

An experiment record proves only that a run is reproducible. It does not prove an edge. Promotion
criteria must be defined before PHASE 5 benchmark results are inspected. Later strategy families
must beat appropriate benchmarks out of sample after the same fees, slippage, funding and risk
constraints. Failure means `REJECTED`; insufficient data means `INCONCLUSIVE`.

Walk-forward, robustness, Monte Carlo and multiple-testing requirements remain binding as defined
in [`PHASE_0_ARCHITECTURE_RESEARCH.md`](PHASE_0_ARCHITECTURE_RESEARCH.md). Frozen PHASE 4 metric
definitions and artifact rules are in [`ANALYTICS.md`](ANALYTICS.md).

## Benchmark rule frozen in PHASE 5

Buy & Hold, seeded Random Entry, Simple Trend Following and Simple Mean Reversion run through the
same target compiler, fixed sizing, execution assumptions, analytics and experiment registry.
Random Entry is a distribution, never a favorable single seed. The first 100-seed control is not a
substitute for the later 10,000-run Monte Carlo requirement. Rules and fixed parameters are in
[`BENCHMARKS.md`](BENCHMARKS.md).

## First candidate protocol frozen in PHASE 6

One dual-channel trend hypothesis and one 55/20 parameter point are registered. TRAIN,
VALIDATION and sealed TEST windows, the BTC/ETH/SOL × 1h/4h matrix, primary metric, activity floor
and benchmark/drawdown gate were fixed before real results. No parameter search is permitted.
Synthetic evidence is structurally incapable of advancement. The exact protocol is in
[`STRATEGY_FAMILY_1.md`](STRATEGY_FAMILY_1.md).

The family cannot receive a real decision until complete curated data and historical funding are
available. A pass would authorize only PHASE 7 robustness analysis; it would not establish an
edge or permit paper/live trading.
