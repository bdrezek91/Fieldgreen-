"""Compile framework-neutral benchmark targets into auditable order intents."""

from __future__ import annotations

from decimal import Decimal

from ai_trading_lab.backtesting.contracts import OrderIntent, OrderType, Side
from ai_trading_lab.benchmarks.contracts import BenchmarkSignal, FixedQuantityPolicy
from ai_trading_lab.data.contracts import Candle, Instrument


class BenchmarkCompilationError(ValueError):
    """Raised when fair next-bar execution cannot be guaranteed."""


def compile_signals(
    signals: tuple[BenchmarkSignal, ...],
    candles: tuple[Candle, ...],
    instrument: Instrument,
    sizing: FixedQuantityPolicy,
    *,
    max_bar_participation: Decimal,
) -> tuple[OrderIntent, ...]:
    """Compile target transitions, rejecting timing, precision and liquidity ambiguity."""
    rows = tuple(sorted(candles, key=lambda item: item.open_time))
    close_index = {item.close_time: index for index, item in enumerate(rows)}
    if sizing.quantity % instrument.quantity_step != 0:
        raise BenchmarkCompilationError("fixed quantity violates instrument quantity_step")
    if not instrument.min_order_quantity <= sizing.quantity <= instrument.max_order_quantity:
        raise BenchmarkCompilationError("fixed quantity violates instrument order limits")
    ordered = tuple(sorted(signals, key=lambda item: item.generated_at))
    if len({item.generated_at for item in ordered}) != len(ordered):
        raise BenchmarkCompilationError("only one target change is allowed per candle close")
    current_units = 0
    orders: list[OrderIntent] = []
    for ordinal, signal in enumerate(ordered, start=1):
        index = close_index.get(signal.generated_at)
        if signal.symbol != instrument.symbol or index is None or index + 1 >= len(rows):
            raise BenchmarkCompilationError("signal must match a known non-final candle close")
        target_units = signal.target.units
        delta = target_units - current_units
        if delta == 0:
            raise BenchmarkCompilationError("redundant target signal")
        quantity = sizing.quantity * abs(delta)
        if quantity > instrument.max_order_quantity:
            raise BenchmarkCompilationError("target transition exceeds maximum order quantity")
        next_bar = rows[index + 1]
        if quantity * next_bar.open < instrument.min_notional:
            raise BenchmarkCompilationError("target transition is below minimum notional")
        capacity = next_bar.volume * max_bar_participation
        if quantity > capacity:
            raise BenchmarkCompilationError("next-bar volume cannot guarantee a complete fill")
        orders.append(
            OrderIntent(
                client_order_id=f"BENCH-{ordinal:06d}",
                symbol=instrument.symbol,
                side=Side.BUY if delta > 0 else Side.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
                submitted_at=signal.generated_at,
                reduce_only=target_units == 0,
            )
        )
        current_units = target_units
    if current_units != 0:
        raise BenchmarkCompilationError("benchmark must finish with a FLAT target")
    return tuple(orders)
