# Analytics and experiment tracking

Status: PHASE 4 implementation complete. No benchmark or alpha strategy exists.

## Evidence flow

`BacktestAnalytics` accepts only an owned `BacktestRequest` and matching canonical
`BacktestResult`. It reconstructs closed trades from fills, calculates versioned portfolio
statistics and returns `AnalyticsResult`. It does not read engine internals and does not decide
whether a strategy should be promoted.

Before calculating metrics it verifies exact accounting identities: fill fees equal reported fees,
reconstructed gross trade PnL equals reported realized PnL, cash reconciles from initial capital,
fees and funding, and equity equals cash plus unrealized PnL. Inconsistent evidence fails closed.

`ExperimentStore` then reserves a monotonic ID in SQLite and publishes an immutable evidence
bundle:

```text
artifacts/
  backtests/bt-*.json
  experiments/
    registry.sqlite3
    EXP-000001/
      manifest.json
      metrics.json
      trades.parquet
      report.md
```

SQLite is deliberately limited to identity, lifecycle and lookup on one VPS. Bulk evidence stays
in files. `AUTOINCREMENT` plus `BEGIN IMMEDIATE` prevents duplicate allocation under concurrent
writers. A failed publication remains in the registry as `FAILED`; its ID is never reused.
PostgreSQL remains the migration target only when multiple workers or hosts require coordination.

## Reproducibility envelope

Every experiment manifest records:

- `EXP-*` ID and UTC timestamp;
- Git commit, hypothesis ID and strategy version;
- dataset version, exact date range, symbols, timeframes and candle count;
- parameters;
- backtest run ID, engine and assumptions versions;
- complete execution assumptions, including fees, spread, slippage, leverage and latency;
- funding and mark events used by the run;
- metric version and trade count;
- SHA-256 of the canonical request and every evidence artifact;
- explicit verdict and written decision reason.

The directory is published by atomic rename. `manifest.json` is the bundle authority and its hash
is stored in the registry. Backtest JSON uses write-once semantics and cannot be silently replaced.

## Trade reconstruction

A closed `TradeRecord` is emitted for each fill quantity that reduces an open net position.
Same-direction fills update the weighted average entry. Partial closes allocate the existing entry
fee pro rata. Exit fees are allocated by the closing share of the fill. A position-flipping fill
first closes the old direction and then opens the remainder in the new direction.

Funding remains a portfolio cash flow and is not assigned arbitrarily to individual trades.
Consequently closed-trade net PnL and final portfolio equity answer different questions and both
are retained.

## Frozen metric definitions — `performance-metrics-v1`

| Metric | Definition |
|---|---|
| Trades | number of reconstructed closed trade records |
| Net Return | `final_equity / initial_cash - 1` |
| CAGR | exact elapsed-time annualization using 365.25 days; null if final equity is non-positive |
| Win Rate | profitable closed trades divided by all closed trades |
| Average Win/Loss | arithmetic mean of positive/negative closed-trade net PnL |
| Expectancy | arithmetic mean of all closed-trade net PnL |
| Profit Factor | sum of wins divided by absolute sum of losses; null without losses |
| Sharpe | mean daily return / sample standard deviation × √365; zero risk-free rate |
| Sortino | mean daily return / downside deviation × √365; target return zero |
| Calmar | CAGR divided by positive maximum-drawdown magnitude |
| Max Drawdown | largest peak-to-trough percentage loss, reported as a positive magnitude |
| Ulcer Index | square root of mean squared drawdown over unique marked-equity timestamps |
| Exposure | seconds with any non-zero portfolio position / test-window seconds |
| Turnover | gross fill notional; ratio divides it by mean of initial and final equity |
| Fees | total fill fees from the canonical result |
| Funding Costs | negative of net funding cash flow; debit positive, credit negative |
| Losing Streak | maximum consecutive closed trades with negative net PnL |

Daily risk returns use the last marked equity per UTC day and carry the previous equity across days
without a new mark. Very short tests can produce mathematically valid but economically meaningless
CAGR, Sharpe or Sortino; research reports must interpret them together with duration.

## Required nulls, not fabricated values

`Average R`, `Median R`, `MAE` and `MFE` are present in the schema but currently `null` and listed
in `unavailable_metrics`. The PHASE 3 order/fill contract does not contain initial planned risk or
the full marked path of each reconstructed trade. PHASE 4 will not infer those values from a later
stop, from realized loss or from bar extremes. A future signal/risk contract must supply point-in-
time initial risk, and a path-aware analyzer must calculate excursions without leakage.

## Verdicts

Every experiment must be labeled manually and audibly as one of:

- `PASSED` — predefined evidence criteria were satisfied;
- `REJECTED` — evidence falsified the hypothesis or violated a gate;
- `INCONCLUSIVE` — evidence is insufficient or ambiguous.

Profit alone never selects the verdict. A non-empty decision reason is mandatory. The PHASE 4
smoke run is always `INCONCLUSIVE` because it tests infrastructure, not a trading hypothesis.

## Phase boundary

PHASE 4 does not add benchmarks, parameter search, Monte Carlo, walk-forward, regimes, strategies
or ML. Those later stages will consume this evidence contract rather than redefine metrics after
seeing results.
