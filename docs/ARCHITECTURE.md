# Architecture

The accepted PHASE 0 architecture is defined in
[`PHASE_0_ARCHITECTURE_RESEARCH.md`](PHASE_0_ARCHITECTURE_RESEARCH.md).

PHASE 1 established the repository, tooling and safety boundary. PHASE 2 adds the first owned
domain contracts and public data adapter:

```text
ai_trading_lab.data.contracts     framework-neutral Candle/Instrument/Timeframe
ai_trading_lab.data.adapters      official Bybit V5 public boundary
ai_trading_lab.data.validation    deterministic integrity policy
ai_trading_lab.data.resampling    1m-to-HTF aggregation and parity
ai_trading_lab.data.storage       immutable Parquet/raw data lake
ai_trading_lab.data.manifest      content identity and lineage
ai_trading_lab.data.pipeline      raw -> normalized -> curated/quarantine orchestration
```

The research heartbeat remains network-isolated. Public ingestion is an explicit one-shot command
with a dedicated persistent volume. Backtesting, risk, portfolio, strategy and execution are still
intentionally absent.

Dependency rule: future domain code must not import exchange or backtesting framework types.
Adapters may depend on the domain, never the reverse.

Only curated, manifested data may cross the future Data-to-Backtest boundary. Provider response
types and storage-library types may not leak into strategies or backtest contracts.
