"""Deterministic candle resampling and provider parity checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_lab.data.contracts import Candle, Timeframe


@dataclass(frozen=True, slots=True)
class ParityMismatch:
    """A field-level mismatch between derived and provider-native candles."""

    open_time: datetime
    field: str
    derived: Decimal
    native: Decimal


def resample_candles(candles: tuple[Candle, ...], target: Timeframe) -> tuple[Candle, ...]:
    """Aggregate complete aligned source groups into a higher timeframe."""
    if not candles:
        return ()
    source = candles[0].timeframe
    if target.minutes <= source.minutes or target.minutes % source.minutes:
        raise ValueError("target timeframe must be a larger exact multiple of source timeframe")
    if any(c.symbol != candles[0].symbol or c.timeframe != source for c in candles):
        raise ValueError("resampling requires one homogeneous series")

    ratio = target.minutes // source.minutes
    buckets: dict[datetime, list[Candle]] = {}
    for candle in sorted(candles, key=lambda item: item.open_time):
        epoch_seconds = int(candle.open_time.timestamp())
        bucket_seconds = target.minutes * 60
        bucket_start = datetime.fromtimestamp(
            epoch_seconds - epoch_seconds % bucket_seconds, tz=UTC
        )
        buckets.setdefault(bucket_start, []).append(candle)

    output: list[Candle] = []
    for bucket_start, group in sorted(buckets.items()):
        expected_times = tuple(bucket_start + source.duration * index for index in range(ratio))
        actual_times = tuple(item.open_time for item in group)
        if len(group) != ratio or actual_times != expected_times:
            continue
        output.append(
            Candle(
                symbol=group[0].symbol,
                timeframe=target,
                open_time=bucket_start,
                open=group[0].open,
                high=max(item.high for item in group),
                low=min(item.low for item in group),
                close=group[-1].close,
                volume=sum((item.volume for item in group), start=Decimal(0)),
                turnover=sum((item.turnover for item in group), start=Decimal(0)),
                source=f"resampled:{source.value}",
            )
        )
    return tuple(output)


def compare_candle_parity(
    derived: tuple[Candle, ...], native: tuple[Candle, ...], *, tolerance: Decimal = Decimal(0)
) -> tuple[ParityMismatch, ...]:
    """Compare overlapping candles field-by-field within an explicit tolerance."""
    native_by_time = {candle.open_time: candle for candle in native}
    mismatches: list[ParityMismatch] = []
    for candle in derived:
        peer = native_by_time.get(candle.open_time)
        if peer is None:
            continue
        for field in ("open", "high", "low", "close", "volume", "turnover"):
            left = getattr(candle, field)
            right = getattr(peer, field)
            if abs(left - right) > tolerance:
                mismatches.append(ParityMismatch(candle.open_time, field, left, right))
    return tuple(mismatches)
