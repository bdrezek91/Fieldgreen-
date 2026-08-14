# Strategy Family 1 — Dual-Channel Trend

Status: PHASE 6 protocol and implementation frozen; real-market conclusion unavailable.

## Falsifiable hypothesis

`HYP-TREND-DUAL-CHANNEL-001`: strong directional breakouts persist through delayed market
reaction, while loss of a shorter price channel identifies decay before a full opposite breakout.

This is a deterministic time-series trend hypothesis, not a claim that Donchian channels create
an edge. Exactly one parameter point was registered before real validation evidence was inspected:

| Parameter | Frozen value |
|---|---:|
| Entry lookback | 55 closed bars |
| Exit lookback | 20 closed bars |
| Direction | symmetric long and short |
| Decision time | candle close |
| Earliest fill | next eligible bar open |
| Initial cash | 100,000 USDT |
| Fixed quantity | BTC 0.1; ETH 1; SOL 10 |
| Leverage | 1× |

At time `t`, channels exclude candle `t`; only completed history through `t-1` is used. A close
above/below the prior 55-bar channel targets long/short. An existing position exits when price
loses the opposite prior 20-bar channel. The declared run ends flat for accounting; this final
flattening is administrative, not alpha.

## Frozen chronology and matrix

All windows are half-open UTC intervals:

| Role | Start | End | Access rule |
|---|---|---|---|
| TRAIN | 2022-01-01 | 2024-01-01 | hypothesis development only |
| VALIDATION | 2024-01-01 | 2025-01-01 | one frozen gate evaluation |
| TEST | 2025-01-01 | 2026-01-01 | **SEALED until PHASE 7** |

The required validation matrix contains BTCUSDT, ETHUSDT and SOLUSDT at 1h and 4h: exactly six
cells. Evidence must use immutable curated Bybit USDT-perpetual datasets, complete historical
funding, 1h mark-price history, an explicit instrument snapshot, identical execution assumptions,
and the PHASE 5 controls. Synthetic data can test plumbing only and returns `INCONCLUSIVE`.

## Gate fixed before results

Primary metric: median candidate net return across the six validation cells.

Activity floor: at least 60 candidate trades in total. Below it, or with an incomplete/duplicate
matrix, the result is `INCONCLUSIVE`. To advance to PHASE 7, all conditions must hold:

- positive candidate net return in at least four of six cells;
- candidate net return above Simple Trend Following in at least four cells;
- candidate net return above the Random Entry p95 return in at least four cells;
- median candidate return above median Simple Trend Following return;
- median candidate maximum drawdown no greater than the larger of 20% and 1.25 times the median
  Simple Trend Following drawdown.

A complete, sufficiently active matrix that fails any condition is `REJECTED`. Passing yields
`ADVANCE_TO_PHASE_7`, which means robustness work is justified—not that an edge has been proven.

## Multiple-testing ledger

PHASE 6 registers one family, one hypothesis and one parameter point. No grid search, favorable
seed selection or TEST inspection is allowed. Any later change creates a new hypothesis/version
and counts as another trial. PBO, Deflated Sharpe, bootstrap/Reality Check and 10,000-run Monte
Carlo remain PHASE 7 work and must use the complete attempt ledger.

## Current evidence

`atl strategy self-test` runs the four PHASE 5 controls plus the candidate on synthetic candles,
records 104 immutable experiments and proves deterministic integration. It is deliberately
`INCONCLUSIVE`. Funding/mark ingestion and the one-shot six-cell runner now exist, but the managed
development environment cannot reach `api.bybit.com`; no dataset was fabricated. The gate remains
`INCONCLUSIVE`, and TEST is unopened.
