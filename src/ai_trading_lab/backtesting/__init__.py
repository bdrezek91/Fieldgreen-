"""Framework-neutral backtesting contracts and reference event kernel."""

from ai_trading_lab.backtesting.contracts import BacktestRequest, BacktestResult, OrderIntent
from ai_trading_lab.backtesting.engine import ReferenceBarBacktestEngine

__all__ = [
    "BacktestRequest",
    "BacktestResult",
    "OrderIntent",
    "ReferenceBarBacktestEngine",
]
