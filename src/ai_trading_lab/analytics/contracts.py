"""Stable analytics contracts independent of reporting and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TradeDirection(StrEnum):
    """Direction of a reconstructed closed trade."""

    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One closed trade reconstructed from canonical fills."""

    trade_id: str
    symbol: str
    direction: TradeDirection
    entry_time: datetime
    exit_time: datetime
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    net_pnl: Decimal
    return_on_entry_notional: Decimal
    initial_risk: Decimal | None = None
    r_multiple: Decimal | None = None
    mae: Decimal | None = None
    mfe: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Versioned portfolio and closed-trade statistics."""

    trades: int
    net_return: Decimal
    cagr: Decimal | None
    win_rate: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    sharpe: Decimal | None
    sortino: Decimal | None
    calmar: Decimal | None
    max_drawdown: Decimal
    ulcer_index: Decimal
    average_r: Decimal | None
    median_r: Decimal | None
    longest_losing_streak: int
    exposure: Decimal
    time_in_market_seconds: Decimal
    turnover_notional: Decimal
    turnover_ratio: Decimal | None
    fees: Decimal
    funding_costs: Decimal
    mae: Decimal | None
    mfe: Decimal | None
    unavailable_metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalyticsResult:
    """Canonical analytics evidence for one backtest result."""

    metric_version: str
    backtest_run_id: str
    trades: tuple[TradeRecord, ...]
    metrics: PerformanceMetrics
