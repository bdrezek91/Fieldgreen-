"""Deterministic trade reconstruction and performance statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from ai_trading_lab.analytics.contracts import (
    AnalyticsResult,
    PerformanceMetrics,
    TradeDirection,
    TradeRecord,
)
from ai_trading_lab.backtesting.contracts import BacktestRequest, BacktestResult, Fill

METRIC_VERSION = "performance-metrics-v1"
SECONDS_PER_YEAR = Decimal("31557600")
DAYS_PER_YEAR = Decimal("365")


class AnalyticsConfigurationError(ValueError):
    """Raised when analytics inputs do not describe the same run."""


@dataclass(slots=True)
class _OpenPosition:
    quantity: Decimal = Decimal(0)
    average_price: Decimal | None = None
    entry_time: datetime | None = None
    entry_fee: Decimal = Decimal(0)


class BacktestAnalytics:
    """Calculate metrics only from canonical request and result evidence."""

    def analyze(self, request: BacktestRequest, result: BacktestResult) -> AnalyticsResult:
        """Reconstruct closed trades and calculate the frozen metric set."""
        self._validate(request, result)
        trades = _reconstruct_trades(result.fills)
        self._validate_accounting(result, trades)
        metrics = _performance_metrics(request, result, trades)
        return AnalyticsResult(METRIC_VERSION, result.run_id, trades, metrics)

    @staticmethod
    def _validate(request: BacktestRequest, result: BacktestResult) -> None:
        if request.dataset_version != result.dataset_version:
            raise AnalyticsConfigurationError("request and result dataset versions differ")
        if not request.candles:
            raise AnalyticsConfigurationError("analytics require candles")
        if result.initial_cash <= 0:
            raise AnalyticsConfigurationError("initial cash must be positive")
        start = min(item.open_time for item in request.candles)
        end = max(item.close_time for item in request.candles)
        for fill in result.fills:
            if fill.timestamp.tzinfo is None or fill.timestamp.utcoffset() is None:
                raise AnalyticsConfigurationError("fill timestamps must be timezone-aware")
            if not start <= fill.timestamp <= end:
                raise AnalyticsConfigurationError("fill timestamp is outside the test window")
            if fill.quantity <= 0 or fill.price <= 0 or fill.fee < 0:
                raise AnalyticsConfigurationError("fill quantity, price and fee are invalid")

    @staticmethod
    def _validate_accounting(result: BacktestResult, trades: tuple[TradeRecord, ...]) -> None:
        fill_fees = sum((fill.fee for fill in result.fills), Decimal(0))
        if fill_fees != result.total_fees:
            raise AnalyticsConfigurationError("fill fees do not match result total_fees")
        reconstructed = sum((trade.gross_pnl for trade in trades), Decimal(0))
        if reconstructed != result.realized_pnl:
            raise AnalyticsConfigurationError(
                "reconstructed trade PnL does not match result realized_pnl"
            )
        expected_cash = (
            result.initial_cash + result.realized_pnl - result.total_fees + result.total_funding
        )
        if expected_cash != result.final_cash:
            raise AnalyticsConfigurationError("result cash violates the accounting identity")
        if result.final_cash + result.unrealized_pnl != result.final_equity:
            raise AnalyticsConfigurationError("result equity violates the accounting identity")


def _reconstruct_trades(fills: tuple[Fill, ...]) -> tuple[TradeRecord, ...]:
    positions: dict[str, _OpenPosition] = {}
    records: list[TradeRecord] = []
    for fill in sorted(fills, key=lambda item: (item.timestamp, item.fill_id)):
        position = positions.setdefault(fill.symbol, _OpenPosition())
        signed = fill.quantity * fill.side.sign
        if position.quantity == 0 or position.quantity * signed > 0:
            old_notional = abs(position.quantity) * (position.average_price or Decimal(0))
            new_quantity = position.quantity + signed
            position.average_price = (old_notional + fill.quantity * fill.price) / abs(new_quantity)
            position.entry_time = position.entry_time or fill.timestamp
            position.entry_fee += fill.fee
            position.quantity = new_quantity
            continue

        old_quantity = position.quantity
        old_abs = abs(old_quantity)
        closing = min(old_abs, fill.quantity)
        exit_fee = fill.fee * closing / fill.quantity
        entry_fee = position.entry_fee * closing / old_abs
        average_price = position.average_price or fill.price
        direction_sign = Decimal(1) if old_quantity > 0 else Decimal(-1)
        gross = closing * (fill.price - average_price) * direction_sign
        net = gross - entry_fee - exit_fee
        entry_notional = closing * average_price
        records.append(
            TradeRecord(
                trade_id=f"TR-{len(records) + 1:08d}",
                symbol=fill.symbol,
                direction=(TradeDirection.LONG if old_quantity > 0 else TradeDirection.SHORT),
                entry_time=position.entry_time or fill.timestamp,
                exit_time=fill.timestamp,
                quantity=closing,
                entry_price=average_price,
                exit_price=fill.price,
                gross_pnl=gross,
                entry_fee=entry_fee,
                exit_fee=exit_fee,
                net_pnl=net,
                return_on_entry_notional=net / entry_notional,
            )
        )
        position.entry_fee -= entry_fee
        new_quantity = old_quantity + signed
        if new_quantity == 0:
            position.quantity = Decimal(0)
            position.average_price = None
            position.entry_time = None
            position.entry_fee = Decimal(0)
        elif old_quantity * new_quantity < 0:
            position.quantity = new_quantity
            position.average_price = fill.price
            position.entry_time = fill.timestamp
            position.entry_fee = fill.fee - exit_fee
        else:
            position.quantity = new_quantity
    return tuple(records)


def _performance_metrics(
    request: BacktestRequest,
    result: BacktestResult,
    trades: tuple[TradeRecord, ...],
) -> PerformanceMetrics:
    net_return = result.final_equity / result.initial_cash - Decimal(1)
    start = min(item.open_time for item in request.candles)
    end = max(item.close_time for item in request.candles)
    duration = Decimal(str((end - start).total_seconds()))
    cagr = _cagr(result.initial_cash, result.final_equity, duration)
    wins = tuple(item.net_pnl for item in trades if item.net_pnl > 0)
    losses = tuple(item.net_pnl for item in trades if item.net_pnl < 0)
    pnls = tuple(item.net_pnl for item in trades)
    final_day = (end - timedelta(microseconds=1)).date()
    daily_returns = _daily_returns(start.date(), final_day, result)
    sharpe = _sharpe(daily_returns)
    sortino = _sortino(daily_returns)
    max_drawdown, ulcer = _drawdown_metrics(result)
    exposure_seconds = _exposure_seconds(result.fills, start, end)
    turnover = sum((fill.quantity * fill.price for fill in result.fills), start=Decimal(0))
    average_equity = (result.initial_cash + result.final_equity) / Decimal(2)
    r_values = tuple(item.r_multiple for item in trades if item.r_multiple is not None)
    mae_values = tuple(item.mae for item in trades if item.mae is not None)
    mfe_values = tuple(item.mfe for item in trades if item.mfe is not None)
    unavailable: list[str] = []
    if not trades or len(r_values) != len(trades):
        unavailable.extend(("average_r", "median_r"))
    if not trades or len(mae_values) != len(trades):
        unavailable.append("mae")
    if not trades or len(mfe_values) != len(trades):
        unavailable.append("mfe")
    return PerformanceMetrics(
        trades=len(trades),
        net_return=net_return,
        cagr=cagr,
        win_rate=Decimal(len(wins)) / Decimal(len(trades)) if trades else None,
        average_win=_mean(wins),
        average_loss=_mean(losses),
        expectancy=_mean(pnls),
        profit_factor=(sum(wins, Decimal(0)) / abs(sum(losses, Decimal(0))) if losses else None),
        sharpe=sharpe,
        sortino=sortino,
        calmar=(cagr / max_drawdown if cagr is not None and max_drawdown > 0 else None),
        max_drawdown=max_drawdown,
        ulcer_index=ulcer,
        average_r=_mean(r_values),
        median_r=_median(r_values),
        longest_losing_streak=_longest_losing_streak(pnls),
        exposure=exposure_seconds / duration if duration > 0 else Decimal(0),
        time_in_market_seconds=exposure_seconds,
        turnover_notional=turnover,
        turnover_ratio=turnover / average_equity if average_equity > 0 else None,
        fees=result.total_fees,
        funding_costs=-result.total_funding,
        mae=_mean(mae_values),
        mfe=_mean(mfe_values),
        unavailable_metrics=tuple(unavailable),
    )


def _cagr(initial: Decimal, final: Decimal, duration_seconds: Decimal) -> Decimal | None:
    if final <= 0 or duration_seconds <= 0:
        return None
    years = duration_seconds / SECONDS_PER_YEAR
    return ((final / initial).ln() / years).exp() - Decimal(1)


def _daily_returns(start: date, end: date, result: BacktestResult) -> tuple[Decimal, ...]:
    closes = {point.timestamp.date(): point.equity for point in result.equity_curve}
    returns: list[Decimal] = []
    previous = result.initial_cash
    current = start
    while current <= end:
        equity = closes.get(current, previous)
        if previous != 0:
            returns.append(equity / previous - Decimal(1))
        previous = equity
        current += timedelta(days=1)
    return tuple(returns)


def _sharpe(returns: tuple[Decimal, ...]) -> Decimal | None:
    deviation = _sample_deviation(returns)
    mean = _mean(returns)
    return mean / deviation * DAYS_PER_YEAR.sqrt() if mean is not None and deviation else None


def _sortino(returns: tuple[Decimal, ...]) -> Decimal | None:
    if not returns:
        return None
    downside = (
        sum((min(item, Decimal(0)) ** 2 for item in returns), Decimal(0)) / Decimal(len(returns))
    ).sqrt()
    mean = _mean(returns)
    return mean / downside * DAYS_PER_YEAR.sqrt() if mean is not None and downside else None


def _drawdown_metrics(result: BacktestResult) -> tuple[Decimal, Decimal]:
    coalesced = {point.timestamp: point.equity for point in result.equity_curve}
    values = (result.initial_cash, *(coalesced[key] for key in sorted(coalesced)))
    peak = values[0]
    drawdowns: list[Decimal] = []
    for value in values:
        peak = max(peak, value)
        drawdowns.append((peak - value) / peak if peak > 0 else Decimal(0))
    maximum = max(drawdowns, default=Decimal(0))
    ulcer = (sum((item**2 for item in drawdowns), Decimal(0)) / Decimal(len(drawdowns))).sqrt()
    return maximum, ulcer


def _exposure_seconds(fills: tuple[Fill, ...], start: datetime, end: datetime) -> Decimal:
    positions: dict[str, Decimal] = {}
    previous = start
    exposed = Decimal(0)
    for fill in sorted(fills, key=lambda item: (item.timestamp, item.fill_id)):
        if any(quantity != 0 for quantity in positions.values()):
            exposed += Decimal(str((fill.timestamp - previous).total_seconds()))
        positions[fill.symbol] = (
            positions.get(fill.symbol, Decimal(0)) + fill.quantity * fill.side.sign
        )
        previous = fill.timestamp
    if any(quantity != 0 for quantity in positions.values()):
        exposed += Decimal(str((end - previous).total_seconds()))
    return max(exposed, Decimal(0))


def _mean(values: tuple[Decimal, ...]) -> Decimal | None:
    return sum(values, Decimal(0)) / Decimal(len(values)) if values else None


def _median(values: tuple[Decimal, ...]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _sample_deviation(values: tuple[Decimal, ...]) -> Decimal | None:
    if len(values) < 2:
        return None
    mean = _mean(values)
    if mean is None:
        return None
    return (
        sum(((item - mean) ** 2 for item in values), Decimal(0)) / Decimal(len(values) - 1)
    ).sqrt()


def _longest_losing_streak(values: tuple[Decimal, ...]) -> int:
    longest = 0
    current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        longest = max(longest, current)
    return longest
