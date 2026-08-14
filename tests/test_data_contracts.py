"""Tests for framework-neutral data contracts and identity."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_lab.data.contracts import Timeframe, milliseconds, utc_from_milliseconds
from ai_trading_lab.data.manifest import candle_dataset_version, utc_iso


def test_timeframe_mappings_are_explicit() -> None:
    assert [item.minutes for item in Timeframe] == [1, 5, 15, 60, 240, 1_440]
    assert [item.bybit_code for item in Timeframe] == ["1", "5", "15", "60", "240", "D"]
    assert Timeframe.FOUR_HOURS.duration.total_seconds() == 14_400


def test_timestamp_roundtrip_uses_utc() -> None:
    value = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    assert utc_from_milliseconds(milliseconds(value)) == value
    assert utc_iso(value) == "2026-01-01T12:30:00+00:00"
    assert utc_iso(None) is None


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        milliseconds(datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_iso(datetime(2026, 1, 1))


def test_dataset_identity_is_order_independent_and_context_sensitive(candle_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (candle_factory(0), candle_factory(1, close=Decimal("102")))
    forward = candle_dataset_version(candles, transformation="v1", identity="window-a")
    reverse = candle_dataset_version(
        tuple(reversed(candles)), transformation="v1", identity="window-a"
    )
    assert forward == reverse
    assert forward.startswith("DS-")
    assert forward != candle_dataset_version(candles, transformation="v1", identity="window-b")
