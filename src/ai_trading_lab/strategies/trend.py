"""First falsifiable candidate: symmetric dual-channel trend following."""

from __future__ import annotations

from dataclasses import dataclass

from ai_trading_lab.data.contracts import Candle
from ai_trading_lab.signals.contracts import PositionSignal, TargetPosition


@dataclass(frozen=True, slots=True)
class DualChannelTrend:
    """Enter on a long channel and exit on loss of a shorter channel."""

    entry_lookback: int = 55
    exit_lookback: int = 20
    name: str = "DUAL_CHANNEL_TREND"
    version: str = "dual-channel-trend-v1"

    def __post_init__(self) -> None:
        if self.exit_lookback < 2 or self.entry_lookback <= self.exit_lookback:
            raise ValueError("entry lookback must exceed an exit lookback of at least two")

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        """Return the only frozen parameter point; no PHASE 6 search is allowed."""
        return (
            ("entry_lookback", str(self.entry_lookback)),
            ("exit_lookback", str(self.exit_lookback)),
        )

    def generate(self, candles: tuple[Candle, ...]) -> tuple[PositionSignal, ...]:
        """Generate symmetric long/short targets using closed prefix data only."""
        rows = _ordered(candles)
        target = TargetPosition.FLAT
        signals: list[PositionSignal] = []
        for index in range(self.entry_lookback, len(rows) - 2):
            candle = rows[index]
            entry_window = rows[index - self.entry_lookback : index]
            exit_window = rows[index - self.exit_lookback : index]
            entry_high = max(item.high for item in entry_window)
            entry_low = min(item.low for item in entry_window)
            exit_high = max(item.high for item in exit_window)
            exit_low = min(item.low for item in exit_window)
            desired = target
            reason = "hold"
            if candle.close > entry_high:
                desired, reason = TargetPosition.LONG, "entry-channel-up-breakout"
            elif candle.close < entry_low:
                desired, reason = TargetPosition.SHORT, "entry-channel-down-breakout"
            elif target is TargetPosition.LONG and candle.close < exit_low:
                desired, reason = TargetPosition.FLAT, "long-exit-channel-loss"
            elif target is TargetPosition.SHORT and candle.close > exit_high:
                desired, reason = TargetPosition.FLAT, "short-exit-channel-loss"
            if desired is not target:
                signals.append(PositionSignal(candle.symbol, candle.close_time, desired, reason))
                target = desired
        if target is not TargetPosition.FLAT:
            signals.append(
                PositionSignal(
                    rows[-2].symbol,
                    rows[-2].close_time,
                    TargetPosition.FLAT,
                    "forced-test-window-exit",
                )
            )
        return tuple(signals)


def _ordered(candles: tuple[Candle, ...]) -> tuple[Candle, ...]:
    if len(candles) < 3:
        raise ValueError("a candidate run requires at least three candles")
    rows = tuple(sorted(candles, key=lambda item: item.open_time))
    if len({item.symbol for item in rows}) != 1:
        raise ValueError("one candidate run must contain exactly one symbol")
    if len({item.timeframe for item in rows}) != 1:
        raise ValueError("one candidate run must contain exactly one timeframe")
    return rows
