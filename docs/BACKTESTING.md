# Backtesting

Status: PHASE 3 reference engine implemented. No alpha strategy exists.

## Purpose and fidelity

The first engine is a small owned correctness kernel, not a promise that OHLC bars reproduce an
exchange matching engine. It consumes explicit orders and produces a canonical fill ledger,
positions and marked equity. Its job is to make assumptions visible, conservative and testable
before strategy research begins.

Planned fidelity tiers remain:

| Tier | Use | Status |
|---|---|---|
| T0 vectorized | fast hypothesis screening; never final evidence | deferred |
| T1 event-driven bars | primary research, walk-forward and portfolio simulation | reference kernel implemented |
| T2 trades/order book | execution-sensitive finalists and fill calibration | deferred |

Only immutable curated datasets with a recorded `DS-*` identity may be used for research evidence.
The engine contract itself accepts validated domain candles so tests stay independent of storage.

## Stable boundary

`BacktestRequest` contains the dataset version, instruments, candles, scheduled `OrderIntent`s,
initial cash, funding, mark prices and versioned `ExecutionAssumptions`. `BacktestResult` contains
the deterministic `BT-*` run ID, fills, ledger, final positions, cash/equity and cost totals.

The project owns these contracts. A future NautilusTrader or another engine adapter must translate
to and from them; framework types cannot leak into data, signals, risk or analytics.

## Event and fill semantics

At the same UTC timestamp, events are applied in this order:

1. funding settlement;
2. mark-price update and optional liquidation check;
3. symbol-sorted bar processing;
4. bar-close marking.

Orders are sorted by UTC submission time and client order ID. An order becomes eligible only when:

`submitted_at + configured_latency <= bar.open_time`

Therefore an intent created at candle close cannot fill at that close. With zero configured
latency it first becomes eligible at the next bar open. Positive latency can defer it by another
bar. There is no ideal close-price execution.

### Market, stop and limit orders

- Market orders fill from the eligible bar open plus adverse half-spread and slippage, rounded
  against the trader to instrument tick size.
- Stop-market orders triggered through a gap start from the bar open; otherwise they start from
  the trigger. The same adverse cost model is then applied.
- A marketable limit is a taker fill and cannot be worse than its limit.
- A resting limit is maker liquidity. The default `CROSS_ONLY` policy requires price to trade
  through the limit; a mere OHLC touch does not prove queue execution. `TOUCH` is an explicit,
  less conservative alternative.
- Bar liquidity is capped by `volume * max_bar_participation` and rounded down to quantity step.
  GTC limits may fill over several bars. A market remainder is canceled; IOC cancels an unfilled
  or partially filled remainder.

### Intrabar ambiguity

OHLC does not reveal whether high or low happened first. If both stop-loss and take-profit in one
OCO group are reachable in the same bar, `WORST_CASE` selects the worse price for the existing
position and cancels the sibling. This removes a common optimistic bias. Arbitrary non-OCO order
priority is deterministic by client order ID, not presented as exchange queue realism.

## Costs, positions and margin

- Maker/taker fees are charged on exact fill notional with `Decimal` arithmetic.
- Positive funding debits longs and credits shorts; negative rates naturally reverse the sign.
- Long, short, partial close and position flips are supported with average entry and realized PnL.
- Reduce-only orders cannot increase or reverse exposure and are capped to the open quantity.
- Tick size, quantity step, minimum quantity and minimum notional are enforced and audited.
- Initial-margin availability is checked from marked portfolio equity and configured leverage.
- Spread, slippage, fee, funding, participation, latency and margin assumptions are versioned in
  every run.

The optional liquidation model is deliberately named `APPROXIMATE`. It uses entry price,
configured leverage, maintenance margin and buffer, then closes at the supplied mark with a
liquidation fee. It does not yet reproduce Bybit risk tiers, cross-margin transfers, insurance or
bankruptcy-price logic. Any leveraged run is `paper_eligible=false`; leverage-one runs are eligible
only as engine evidence, not as an authorization to paper or live trade.

## Reproducibility and audit

Identical immutable input produces the same `BT-*` ID, fill IDs, event ordering and result. The
artifact store writes canonical JSON once under `backtests/bt-*.json`, preserves decimals as
strings, includes the request summary and rejects any overwrite with different bytes. Artifacts
belong on the VPS experiment volume, never in Git.

Run the deterministic, synthetic, non-strategy smoke scenario twice:

```bash
uv run atl backtest self-test
uv run atl backtest self-test
```

The JSON outputs must be identical. CI repeats the same test inside a network-disabled container.

## Bias controls implemented now

- validated and contiguous candle input;
- explicit UTC timestamps;
- close-to-next-open prohibition;
- prefix-invariance test: appending future bars cannot alter past fills, ledger or equity prefix;
- conservative same-bar OCO resolution;
- deterministic multi-symbol ordering;
- immutable dataset and assumptions identity;
- no strategy optimization and no alpha code in PHASE 3.

Survivorship control, train/validation/test orchestration, purging/embargo, walk-forward assembly,
multiple-testing corrections, Monte Carlo and performance metrics belong to later phases.

## Known limitations

- A bar contains no true trade path, queue position, spread history or market depth.
- A single participation cap is a research assumption, not a fill probability model.
- Stop triggering uses OHLC extremes and cannot model gaps between intrabar trades.
- Funding and mark inputs exist as contracts but their historical ingestion is not yet built.
- Margin is isolated-style and simplified; liquidation is explicitly approximate.
- Portfolio risk constraints and correlation limits are not part of the backtester.
- No T0 adapter, Nautilus adapter or T2 replay engine is installed yet.

These limitations must be disclosed in every later report that uses the T1 kernel.
