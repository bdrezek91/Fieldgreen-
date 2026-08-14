# Research Methodology

Status: PHASE 4 evidence foundation implemented; strategy research has not started.

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
