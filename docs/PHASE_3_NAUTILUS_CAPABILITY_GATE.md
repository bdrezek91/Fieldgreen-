# PHASE 3 — NautilusTrader capability gate

**Decision date:** 2026-08-14

**Decision:** `DEFER` as a runtime dependency; retain as the leading future T1/T2 adapter candidate.

## Question

Can NautilusTrader be adopted now as the production backtest kernel without weakening the
project's determinism, next-bar execution rule, stable contracts or reproducibility?

## Current official state

The official release feed inspected on the decision date showed `v1.231.0 Beta` (2026-08-02) and
the paired `2.0.0rc2`; a stable v2 release was not available. An isolated `2.0.0rc2` spike imported
`BacktestEngine`, `BacktestEngineConfig` and `DefaultFillModel`. API inspection confirmed venue
configuration for margin, fill and fee models, latency, liquidity consumption, queue behavior and
liquidation controls. `FundingRateUpdate` carries an instrument, rate and event timestamps.

Primary sources:

- [official releases](https://github.com/nautechsystems/nautilus_trader/releases);
- [backtesting concepts](https://nautilustrader.io/docs/latest/concepts/backtesting/);
- [APIs and repeated runs](https://nautilustrader.io/docs/latest/concepts/backtesting/apis-and-runs/);
- [execution flow](https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/);
- [fill matching](https://nautilustrader.io/docs/latest/concepts/backtesting/fill-prices-and-matching/);
- [bar execution](https://nautilustrader.io/docs/latest/concepts/backtesting/bar-execution/);
- [fill models](https://nautilustrader.io/docs/latest/concepts/backtesting/fill-models/);
- [accounts and margin](https://nautilustrader.io/docs/latest/concepts/backtesting/accounts-and-margin/);
- [Bybit integration](https://nautilustrader.io/docs/latest/integrations/bybit/).

## Gate results

| Capability | Evidence / assessment | Result |
|---|---|---|
| Event-driven shared backtest/live model | central design of the framework | PASS |
| Long/short, margin and leverage | supported through venue/account models | PASS |
| Fees, fill/slippage and latency models | configurable models are exposed | PASS |
| Partial fills and liquidity consumption | supported, including bar volume consumption | PASS |
| Funding events | `FundingRateUpdate` and settlement path documented | PASS |
| Tick/trade/order-book evolution path | native data/event architecture supports higher fidelity | PASS |
| Bybit linear perpetual adapter | documented by official integration | PASS |
| Deterministic repeated runs | documented reset/re-run behavior and deterministic trade IDs | PASS |
| Stable v2 production release | only release candidate observed | FAIL |
| Native next-bar-open for signals emitted in `on_bar` | current-close settlement is possible; no native next-open mode | FAIL |
| True intrabar sequence from OHLC | bars cannot contain the real sequence | LIMITATION |
| Owned framework-neutral contracts | requires an adapter, acceptable but not yet implemented | DEFERRED |

## Alternatives considered at this gate

1. **Pin `2.0.0rc2` now.** Highest immediate capability, but makes an RC a foundational dependency
   and still requires custom scheduling to guarantee the project's close-to-next-open rule.
2. **Adopt the v1 beta line.** More mature operational history, but it is still labeled beta and
   creates a near-term migration burden to v2.
3. **Build a narrow owned reference kernel and keep Nautilus behind a port.** Less feature-rich,
   but freezes semantics under tests and lets a later stable Nautilus release be compared against
   a known correctness oracle.

Option 3 is selected.

## Consequence

PHASE 3 installs no Nautilus dependency. The project owns `OrderIntent`, funding/mark inputs,
execution assumptions, fills, ledger, position/equity output and the `BacktestEngine` protocol.
The T1 reference kernel implements only the semantics needed to validate research plumbing. It is
not a second exchange framework and must stay intentionally small.

Re-open this gate when a stable NautilusTrader v2 release exists. Acceptance then requires:

1. a pinned isolated adapter;
2. golden parity scenarios against the reference kernel;
3. explicit next-bar scheduling outside `on_bar` close execution;
4. funding, partial-fill, OCO ambiguity, margin and liquidation tests;
5. repeated-run equality and canonical-result translation;
6. measured runtime/memory benchmarks on representative multi-symbol data.

Until those conditions pass, NautilusTrader is `INCONCLUSIVE` for production adoption—not
rejected as a technology and not silently assumed to be correct.
