"""Tests for complete-bucket resampling and native parity."""

from decimal import Decimal

import pytest

from ai_trading_lab.data.contracts import Timeframe
from ai_trading_lab.data.resampling import compare_candle_parity, resample_candles


def test_complete_one_minute_bucket_resamples_exactly(candle_factory) -> None:  # type: ignore[no-untyped-def]
    source = tuple(
        candle_factory(
            index,
            open=Decimal(100 + index),
            high=Decimal(102 + index),
            low=Decimal(99 + index),
            close=Decimal(101 + index),
            volume=Decimal(index + 1),
            turnover=Decimal(100 * (index + 1)),
        )
        for index in range(5)
    )
    result = resample_candles(source, Timeframe.FIVE_MINUTES)
    assert len(result) == 1
    candle = result[0]
    assert (candle.open, candle.high, candle.low, candle.close) == (
        Decimal(100),
        Decimal(106),
        Decimal(99),
        Decimal(105),
    )
    assert candle.volume == Decimal(15)
    assert candle.turnover == Decimal(1500)
    assert candle.source == "resampled:1m"


def test_partial_or_gapped_buckets_are_not_emitted(candle_factory) -> None:  # type: ignore[no-untyped-def]
    assert resample_candles((), Timeframe.FIVE_MINUTES) == ()
    assert (
        resample_candles(tuple(candle_factory(i) for i in range(4)), Timeframe.FIVE_MINUTES) == ()
    )
    assert (
        resample_candles(
            (
                candle_factory(0),
                candle_factory(1),
                candle_factory(2),
                candle_factory(3),
                candle_factory(5),
            ),
            Timeframe.FIVE_MINUTES,
        )
        == ()
    )


def test_invalid_resampling_inputs_fail(candle_factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="larger exact multiple"):
        resample_candles((candle_factory(),), Timeframe.ONE_MINUTE)
    with pytest.raises(ValueError, match="homogeneous"):
        resample_candles(
            (candle_factory(0), candle_factory(1, symbol="ETHUSDT")), Timeframe.FIVE_MINUTES
        )


def test_parity_reports_only_out_of_tolerance_fields(candle_factory) -> None:  # type: ignore[no-untyped-def]
    derived = (candle_factory(0), candle_factory(1))
    native = (
        candle_factory(0, close=Decimal("101.01")),
        candle_factory(1, volume=Decimal("12")),
    )
    mismatches = compare_candle_parity(derived, native, tolerance=Decimal("0.02"))
    assert [(item.field, item.native) for item in mismatches] == [("volume", Decimal("12"))]
