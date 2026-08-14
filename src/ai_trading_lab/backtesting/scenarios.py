"""Synthetic non-strategy scenarios used to verify the reference kernel."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai_trading_lab.backtesting.contracts import BacktestRequest, OrderIntent, OrderType, Side
from ai_trading_lab.backtesting.engine import ReferenceBarBacktestEngine
from ai_trading_lab.data.contracts import Candle, Instrument, Timeframe


def reference_smoke_payload() -> dict[str, object]:
    """Run a deterministic next-bar execution scenario and return its fingerprint."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            symbol="BTCUSDT",
            timeframe=Timeframe.ONE_MINUTE,
            open_time=start + timedelta(minutes=index),
            open=Decimal("100") + index,
            high=Decimal("102") + index,
            low=Decimal("99") + index,
            close=Decimal("101") + index,
            volume=Decimal("100"),
            turnover=Decimal("10000"),
            source="synthetic_phase_3_smoke",
        )
        for index in range(3)
    )
    instrument = Instrument(
        symbol="BTCUSDT",
        base_coin="BTC",
        quote_coin="USDT",
        settle_coin="USDT",
        status="Trading",
        contract_type="LinearPerpetual",
        launch_time=datetime(2020, 1, 1, tzinfo=UTC),
        delivery_time=None,
        tick_size=Decimal("0.1"),
        min_price=Decimal("0.1"),
        max_price=Decimal("1000000"),
        quantity_step=Decimal("0.001"),
        min_order_quantity=Decimal("0.001"),
        max_order_quantity=Decimal("1000"),
        min_notional=Decimal("1"),
        min_leverage=Decimal("1"),
        max_leverage=Decimal("100"),
        leverage_step=Decimal("0.01"),
        funding_interval_minutes=480,
        source="synthetic_phase_3_smoke",
    )
    request = BacktestRequest(
        dataset_version="DS-PHASE-3-SMOKE-V1",
        candles=candles,
        instruments=(instrument,),
        orders=(
            OrderIntent(
                client_order_id="SMOKE-ENTRY",
                symbol="BTCUSDT",
                side=Side.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("1"),
                submitted_at=candles[0].close_time,
            ),
        ),
        initial_cash=Decimal("10000"),
    )
    result = ReferenceBarBacktestEngine().run(request)
    fill = result.fills[0]
    return {
        "status": "PASS",
        "engine": result.engine_version,
        "run_id": result.run_id,
        "dataset_version": result.dataset_version,
        "fills": len(result.fills),
        "first_fill_time": fill.timestamp.isoformat(),
        "first_fill_price": str(fill.price),
        "total_fees": str(result.total_fees),
        "final_equity": str(result.final_equity),
        "paper_eligible": result.paper_eligible,
        "live_trading": "BLOCKED",
    }
