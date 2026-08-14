"""Integrity tests covering every required OHLCV failure class."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from ai_trading_lab.data.contracts import FundingRate, Timeframe
from ai_trading_lab.data.validation import CandleValidationPolicy, CandleValidator, FundingValidator

AS_OF = datetime(2026, 1, 2, tzinfo=UTC)


def _codes(report) -> set[str]:  # type: ignore[no-untyped-def]
    return {issue.code for issue in report.issues}


def test_valid_candles_pass(candle_factory) -> None:  # type: ignore[no-untyped-def]
    report = CandleValidator().validate((candle_factory(0), candle_factory(1)), as_of=AS_OF)
    assert report.is_valid
    assert report.error_count == 0
    assert report.warning_count == 0


def test_empty_and_naive_as_of_are_rejected(candle_factory) -> None:  # type: ignore[no-untyped-def]
    report = CandleValidator().validate((), as_of=AS_OF)
    assert not report.is_valid
    assert _codes(report) == {"EMPTY_DATASET"}
    with pytest.raises(ValueError, match="as_of"):
        CandleValidator().validate((candle_factory(),), as_of=datetime(2026, 1, 2))


def test_time_integrity_findings(candle_factory) -> None:  # type: ignore[no-untyped-def]
    non_utc = datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    rows = (
        candle_factory(0, open_time=non_utc),
        candle_factory(0),
        candle_factory(0),
        candle_factory(3, open_time=datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC)),
    )
    codes = _codes(CandleValidator().validate(rows, as_of=AS_OF))
    assert {
        "NON_UTC_TIMESTAMP",
        "DUPLICATE_TIMESTAMP",
        "NON_MONOTONIC_TIME",
        "MISSING_CANDLES",
        "MISALIGNED_TIMESTAMP",
    } <= codes


def test_naive_mixed_and_incomplete_candles(candle_factory) -> None:  # type: ignore[no-untyped-def]
    naive = candle_factory(0, open_time=datetime(2026, 1, 1))
    mixed = candle_factory(
        1,
        symbol="ETHUSDT",
        timeframe=Timeframe.FIVE_MINUTES,
        open_time=datetime(2026, 1, 2, tzinfo=UTC),
    )
    codes = _codes(CandleValidator().validate((naive, mixed), as_of=AS_OF))
    assert {"NAIVE_TIMESTAMP", "MIXED_SERIES", "INCOMPLETE_CANDLE"} <= codes


def test_value_invariants_and_anomaly_findings(candle_factory) -> None:  # type: ignore[no-untyped-def]
    first = candle_factory(0, close=Decimal("10"))
    second = candle_factory(
        1,
        open=Decimal("-1"),
        high=Decimal("2"),
        low=Decimal("3"),
        close=Decimal("100"),
        volume=Decimal("-1"),
        turnover=Decimal("-2"),
    )
    codes = _codes(CandleValidator().validate((first, second), as_of=AS_OF))
    assert {
        "NON_POSITIVE_PRICE",
        "INVALID_OHLC",
        "NEGATIVE_ACTIVITY",
        "ANOMALOUS_RETURN",
    } <= codes


def test_zero_volume_policy_can_warn_or_block(candle_factory) -> None:  # type: ignore[no-untyped-def]
    candle = candle_factory(volume=Decimal(0))
    warning = CandleValidator().validate((candle,), as_of=AS_OF)
    error = CandleValidator(CandleValidationPolicy(zero_volume_is_error=True)).validate(
        (candle,), as_of=AS_OF
    )
    assert warning.is_valid and warning.warning_count == 1
    assert not error.is_valid and error.error_count == 1


def _funding(hour: int, *, symbol: str = "BTCUSDT") -> FundingRate:
    return FundingRate(symbol, datetime(2026, 1, 1, hour, tzinfo=UTC), Decimal("0.0001"))


def test_complete_funding_series_passes() -> None:
    report = FundingValidator().validate(
        (_funding(0), _funding(8), _funding(16)),
        interval_minutes=480,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        as_of=AS_OF,
    )
    assert report.is_valid


def test_funding_validator_fails_closed_on_missing_duplicate_and_boundary() -> None:
    rows = (_funding(8), _funding(8), _funding(16, symbol="ETHUSDT"))
    report = FundingValidator().validate(
        rows,
        interval_minutes=480,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        as_of=AS_OF,
    )
    assert {
        "MISSING_INITIAL_FUNDING",
        "DUPLICATE_FUNDING",
        "NON_MONOTONIC_FUNDING",
        "MIXED_FUNDING_SERIES",
    } <= _codes(report)
    assert not report.is_valid


def test_funding_validator_rejects_empty_and_bad_configuration() -> None:
    empty = FundingValidator().validate(
        (),
        interval_minutes=480,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        as_of=AS_OF,
    )
    assert _codes(empty) == {"EMPTY_FUNDING"}
    with pytest.raises(ValueError, match="timezone-aware"):
        FundingValidator().validate(
            (_funding(0),),
            interval_minutes=480,
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 2, tzinfo=UTC),
            as_of=AS_OF,
        )
    with pytest.raises(ValueError, match="interval"):
        FundingValidator().validate(
            (_funding(0),),
            interval_minutes=0,
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 2, tzinfo=UTC),
            as_of=AS_OF,
        )


def test_funding_validator_reports_alignment_range_rate_and_cadence() -> None:
    odd = FundingRate(
        "BTCUSDT",
        datetime(2026, 1, 1, 9, 1, tzinfo=timezone(timedelta(hours=1))),
        Decimal("NaN"),
    )
    outside = FundingRate("BTCUSDT", datetime(2026, 1, 2, tzinfo=UTC), Decimal("0.0001"))
    report = FundingValidator().validate(
        (_funding(0), odd, outside),
        interval_minutes=480,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        as_of=datetime(2026, 1, 1, 4, tzinfo=UTC),
    )
    assert {
        "NON_UTC_FUNDING_TIMESTAMP",
        "MISALIGNED_FUNDING",
        "UNSETTLED_FUNDING",
        "INVALID_FUNDING_RATE",
        "MISSING_FUNDING",
        "OUTSIDE_FUNDING_WINDOW",
    } <= _codes(report)


def test_candle_window_boundaries_are_required(candle_factory) -> None:  # type: ignore[no-untyped-def]
    report = CandleValidator().validate(
        (candle_factory(1),),
        as_of=AS_OF,
        expected_start=datetime(2026, 1, 1, tzinfo=UTC),
        expected_end=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    assert {"MISSING_INITIAL_CANDLES", "MISSING_FINAL_CANDLES"} <= _codes(report)
