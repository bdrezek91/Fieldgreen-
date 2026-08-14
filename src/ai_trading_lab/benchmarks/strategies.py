"""Frozen, intentionally simple PHASE 5 control benchmarks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from ai_trading_lab.benchmarks.contracts import BenchmarkSignal, TargetPosition
from ai_trading_lab.data.contracts import Candle


def _ordered(candles: tuple[Candle, ...]) -> tuple[Candle, ...]:
    if len(candles) < 3:
        raise ValueError("a benchmark requires at least three candles")
    rows = tuple(sorted(candles, key=lambda item: item.open_time))
    if len({item.symbol for item in rows}) != 1:
        raise ValueError("one benchmark run must contain exactly one symbol")
    if len({item.timeframe for item in rows}) != 1:
        raise ValueError("one benchmark run must contain exactly one timeframe")
    return rows


def _signal(candle: Candle, target: TargetPosition, reason: str) -> BenchmarkSignal:
    return BenchmarkSignal(candle.symbol, candle.close_time, target, reason)


@dataclass(frozen=True, slots=True)
class BuyAndHold:
    """Perpetual long control; funding remains an explicit backtest input."""

    name: str = "BUY_AND_HOLD"
    version: str = "buy-and-hold-v1"

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        return ()

    def generate(self, candles: tuple[Candle, ...]) -> tuple[BenchmarkSignal, ...]:
        rows = _ordered(candles)
        return (
            _signal(rows[0], TargetPosition.LONG, "first-eligible-close"),
            _signal(rows[-2], TargetPosition.FLAT, "forced-test-window-exit"),
        )


@dataclass(frozen=True, slots=True)
class RandomEntry:
    """Reproducible random-direction control using SHA-256, not global RNG state."""

    seed: int
    entry_probability: Decimal = Decimal("0.10")
    holding_bars: int = 5
    name: str = "RANDOM_ENTRY"
    version: str = "random-entry-v1"

    def __post_init__(self) -> None:
        if not Decimal(0) < self.entry_probability <= Decimal(1):
            raise ValueError("entry_probability must be in (0, 1]")
        if self.holding_bars < 1:
            raise ValueError("holding_bars must be positive")

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        return (
            ("entry_probability", str(self.entry_probability)),
            ("holding_bars", str(self.holding_bars)),
            ("seed", str(self.seed)),
        )

    def generate(self, candles: tuple[Candle, ...]) -> tuple[BenchmarkSignal, ...]:
        rows = _ordered(candles)
        signals: list[BenchmarkSignal] = []
        exit_index: int | None = None
        for index, candle in enumerate(rows[:-1]):
            if exit_index is not None:
                if index >= exit_index:
                    signals.append(_signal(candle, TargetPosition.FLAT, "fixed-holding-period"))
                    exit_index = None
                continue
            if index + self.holding_bars >= len(rows) - 1:
                continue
            if _uniform(self.seed, index, "entry") < self.entry_probability:
                target = (
                    TargetPosition.LONG
                    if _uniform(self.seed, index, "direction") < Decimal("0.5")
                    else TargetPosition.SHORT
                )
                signals.append(_signal(candle, target, "seeded-random-entry"))
                exit_index = index + self.holding_bars
        return tuple(signals)


def _uniform(seed: int, index: int, stream: str) -> Decimal:
    digest = hashlib.sha256(f"{seed}:{index}:{stream}".encode()).digest()
    numerator = int.from_bytes(digest[:8], "big")
    return Decimal(numerator) / Decimal(2**64)


@dataclass(frozen=True, slots=True)
class SimpleTrendFollowing:
    """Non-optimized close breakout of the prior Donchian window."""

    lookback: int = 50
    name: str = "SIMPLE_TREND_FOLLOWING"
    version: str = "donchian-close-v1"

    def __post_init__(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be at least two")

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        return (("lookback", str(self.lookback)),)

    def generate(self, candles: tuple[Candle, ...]) -> tuple[BenchmarkSignal, ...]:
        rows = _ordered(candles)
        target = TargetPosition.FLAT
        signals: list[BenchmarkSignal] = []
        for index in range(self.lookback, len(rows) - 2):
            candle = rows[index]
            prior = rows[index - self.lookback : index]
            desired = target
            if candle.close > max(item.high for item in prior):
                desired = TargetPosition.LONG
            elif candle.close < min(item.low for item in prior):
                desired = TargetPosition.SHORT
            if desired is not target:
                signals.append(_signal(candle, desired, "prior-window-close-breakout"))
                target = desired
        if target is not TargetPosition.FLAT:
            signals.append(_signal(rows[-2], TargetPosition.FLAT, "forced-test-window-exit"))
        return tuple(signals)


@dataclass(frozen=True, slots=True)
class SimpleMeanReversion:
    """Non-optimized rolling close z-score control."""

    lookback: int = 20
    entry_z: Decimal = Decimal("2")
    name: str = "SIMPLE_MEAN_REVERSION"
    version: str = "rolling-zscore-v1"

    def __post_init__(self) -> None:
        if self.lookback < 2 or self.entry_z <= 0:
            raise ValueError("lookback must be >= 2 and entry_z positive")

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        return (("entry_z", str(self.entry_z)), ("lookback", str(self.lookback)))

    def generate(self, candles: tuple[Candle, ...]) -> tuple[BenchmarkSignal, ...]:
        rows = _ordered(candles)
        target = TargetPosition.FLAT
        signals: list[BenchmarkSignal] = []
        for index in range(self.lookback - 1, len(rows) - 2):
            candle = rows[index]
            window = tuple(item.close for item in rows[index - self.lookback + 1 : index + 1])
            mean = sum(window, Decimal(0)) / Decimal(len(window))
            variance = sum(((item - mean) ** 2 for item in window), Decimal(0)) / Decimal(
                len(window)
            )
            deviation = variance.sqrt()
            zscore = (candle.close - mean) / deviation if deviation else Decimal(0)
            desired = target
            if target is TargetPosition.FLAT and zscore >= self.entry_z:
                desired = TargetPosition.SHORT
            elif target is TargetPosition.FLAT and zscore <= -self.entry_z:
                desired = TargetPosition.LONG
            elif (target is TargetPosition.LONG and zscore >= 0) or (
                target is TargetPosition.SHORT and zscore <= 0
            ):
                desired = TargetPosition.FLAT
            if desired is not target:
                signals.append(_signal(candle, desired, "rolling-close-zscore"))
                target = desired
        if target is not TargetPosition.FLAT:
            signals.append(_signal(rows[-2], TargetPosition.FLAT, "forced-test-window-exit"))
        return tuple(signals)
