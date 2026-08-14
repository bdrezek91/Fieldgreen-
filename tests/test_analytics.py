"""Tests for canonical trade reconstruction and frozen metric definitions."""

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from ai_trading_lab.analytics.metrics import AnalyticsConfigurationError, BacktestAnalytics
from ai_trading_lab.backtesting.contracts import (
    BacktestRequest,
    BacktestResult,
    EquityPoint,
    Fill,
    LiquidityRole,
    Side,
)


def _fill(
    identifier: int,
    side: Side,
    timestamp: datetime,
    quantity: str,
    price: str,
    fee: str,
) -> Fill:
    return Fill(
        fill_id=f"F-{identifier:08d}",
        client_order_id=f"ORDER-{identifier}",
        symbol="BTCUSDT",
        side=side,
        timestamp=timestamp,
        quantity=Decimal(quantity),
        price=Decimal(price),
        liquidity=LiquidityRole.TAKER,
        fee=Decimal(fee),
    )


def _evidence(candle_factory, instrument_factory):  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index) for index in range(4))
    start = candles[0].open_time
    fills = (
        _fill(1, Side.BUY, start, "2", "100", "2"),
        _fill(2, Side.SELL, start + timedelta(minutes=1), "1", "110", "1.1"),
        _fill(3, Side.SELL, start + timedelta(minutes=2), "2", "90", "1.8"),
        _fill(4, Side.BUY, start + timedelta(minutes=3), "1", "80", "0.8"),
    )
    request = BacktestRequest(
        dataset_version="DS-ANALYTICS",
        candles=candles,
        instruments=(instrument_factory(),),
        orders=(),
        initial_cash=Decimal("1000"),
    )
    curve = (
        EquityPoint(start, Decimal("1000"), Decimal(0), Decimal("1000")),
        EquityPoint(start + timedelta(minutes=1), Decimal("1010"), Decimal(0), Decimal("1010")),
        EquityPoint(start + timedelta(minutes=2), Decimal("990"), Decimal(0), Decimal("990")),
        EquityPoint(start + timedelta(minutes=3), Decimal("1003.1"), Decimal(0), Decimal("1003.1")),
    )
    result = BacktestResult(
        run_id="BT-ANALYTICS",
        dataset_version=request.dataset_version,
        engine_version="test-engine",
        assumptions_version="test-assumptions",
        initial_cash=Decimal("1000"),
        final_cash=Decimal("1003.1"),
        final_equity=Decimal("1003.1"),
        realized_pnl=Decimal("10"),
        unrealized_pnl=Decimal(0),
        total_fees=Decimal("5.7"),
        total_funding=Decimal("-1.2"),
        liquidation_count=0,
        paper_eligible=True,
        fills=fills,
        ledger=(),
        positions=(),
        equity_curve=curve,
    )
    return request, result


def test_trade_reconstruction_handles_partial_close_and_flip(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    request, result = _evidence(candle_factory, instrument_factory)
    analysis = BacktestAnalytics().analyze(request, result)

    assert [trade.direction.value for trade in analysis.trades] == ["LONG", "LONG", "SHORT"]
    assert [trade.net_pnl for trade in analysis.trades] == [
        Decimal("7.9"),
        Decimal("-11.9"),
        Decimal("8.3"),
    ]
    assert analysis.trades[1].entry_fee == Decimal("1")
    assert analysis.trades[1].exit_fee == Decimal("0.9")
    assert analysis.trades[2].entry_fee == Decimal("0.9")


def test_required_metrics_have_frozen_signs_and_definitions(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    request, result = _evidence(candle_factory, instrument_factory)
    metrics = BacktestAnalytics().analyze(request, result).metrics

    assert metrics.trades == 3
    assert metrics.net_return == Decimal("0.0031")
    assert metrics.win_rate == Decimal(2) / Decimal(3)
    assert metrics.average_win == Decimal("8.1")
    assert metrics.average_loss == Decimal("-11.9")
    assert metrics.expectancy == Decimal("1.433333333333333333333333333")
    assert metrics.profit_factor == Decimal("16.2") / Decimal("11.9")
    assert metrics.max_drawdown == Decimal("20") / Decimal("1010")
    assert metrics.longest_losing_streak == 1
    assert metrics.time_in_market_seconds == Decimal("180")
    assert metrics.exposure == Decimal("0.75")
    assert metrics.turnover_notional == Decimal("570")
    assert metrics.fees == Decimal("5.7")
    assert metrics.funding_costs == Decimal("1.2")
    assert metrics.cagr is not None
    assert metrics.average_r is None
    assert metrics.median_r is None
    assert metrics.mae is None
    assert metrics.mfe is None
    assert metrics.unavailable_metrics == ("average_r", "median_r", "mae", "mfe")


def test_daily_risk_metrics_and_no_loss_profit_factor(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    request, result = _evidence(candle_factory, instrument_factory)
    start = request.candles[0].open_time
    request = replace(
        request,
        candles=(
            candle_factory(0),
            candle_factory(1, open_time=start + timedelta(days=1)),
            candle_factory(2, open_time=start + timedelta(days=2)),
        ),
    )
    result = replace(
        result,
        fills=(),
        final_equity=Decimal("1100"),
        final_cash=Decimal("1000"),
        realized_pnl=Decimal(0),
        unrealized_pnl=Decimal("100"),
        total_fees=Decimal(0),
        total_funding=Decimal(0),
        equity_curve=(
            EquityPoint(start, Decimal("1000"), Decimal(0), Decimal("1000")),
            EquityPoint(start + timedelta(days=1), Decimal("900"), Decimal(0), Decimal("900")),
            EquityPoint(start + timedelta(days=2), Decimal("1100"), Decimal(0), Decimal("1100")),
        ),
    )
    metrics = BacktestAnalytics().analyze(request, result).metrics
    assert metrics.sharpe is not None
    assert metrics.sortino is not None
    assert metrics.calmar is not None
    assert metrics.profit_factor is None
    assert metrics.win_rate is None
    assert metrics.exposure == 0


def test_analytics_rejects_mismatched_or_invalid_evidence(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    request, result = _evidence(candle_factory, instrument_factory)
    with pytest.raises(AnalyticsConfigurationError, match="dataset versions differ"):
        BacktestAnalytics().analyze(request, replace(result, dataset_version="DS-OTHER"))
    with pytest.raises(AnalyticsConfigurationError, match="require candles"):
        BacktestAnalytics().analyze(replace(request, candles=()), result)
    with pytest.raises(AnalyticsConfigurationError, match="positive"):
        BacktestAnalytics().analyze(request, replace(result, initial_cash=Decimal(0)))
    with pytest.raises(AnalyticsConfigurationError, match="fill fees"):
        BacktestAnalytics().analyze(request, replace(result, total_fees=Decimal(0)))
    with pytest.raises(AnalyticsConfigurationError, match="reconstructed trade PnL"):
        BacktestAnalytics().analyze(request, replace(result, realized_pnl=Decimal(0)))
    with pytest.raises(AnalyticsConfigurationError, match="accounting identity"):
        BacktestAnalytics().analyze(request, replace(result, final_equity=Decimal("999")))
    with pytest.raises(AnalyticsConfigurationError, match="cash"):
        BacktestAnalytics().analyze(request, replace(result, final_cash=Decimal("999")))
    outside = replace(
        result.fills[0], timestamp=request.candles[0].open_time - timedelta(seconds=1)
    )
    with pytest.raises(AnalyticsConfigurationError, match="outside"):
        BacktestAnalytics().analyze(request, replace(result, fills=(outside, *result.fills[1:])))
    invalid = replace(result.fills[0], fee=Decimal("-1"))
    with pytest.raises(AnalyticsConfigurationError, match="invalid"):
        BacktestAnalytics().analyze(request, replace(result, fills=(invalid, *result.fills[1:])))
    naive = replace(result.fills[0], timestamp=datetime(2026, 1, 1))
    with pytest.raises(AnalyticsConfigurationError, match="timezone-aware"):
        BacktestAnalytics().analyze(request, replace(result, fills=(naive, *result.fills[1:])))
