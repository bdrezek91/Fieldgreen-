# Backtesting

Status: design only. No backtest engine or strategy exists in PHASE 1.

The planned process has three fidelity levels: vectorized hypothesis screening, event-driven
bar simulation and tick/order-book replay for execution-sensitive finalists. A candidate
cannot advance on ideal close-price fills or in-sample results.

NautilusTrader remains a conditional adapter candidate and must pass the capability gate
specified in the PHASE 0 research before adoption.
