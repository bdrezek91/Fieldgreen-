"""Deterministic market-data integrity validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from ai_trading_lab.data.contracts import Candle, FundingRate, MarkPriceCandle


class Severity(StrEnum):
    """Validation issue severity."""

    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class DataIssue:
    """One auditable data-quality finding."""

    code: str
    severity: Severity
    message: str
    symbol: str | None = None
    open_time: datetime | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Complete validation outcome for one candle batch."""

    issues: tuple[DataIssue, ...]
    row_count: int

    @property
    def is_valid(self) -> bool:
        """Return true when no blocking errors were found."""
        return all(issue.severity is not Severity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        """Return the number of blocking errors."""
        return sum(issue.severity is Severity.ERROR for issue in self.issues)

    @property
    def warning_count(self) -> int:
        """Return the number of non-blocking warnings."""
        return sum(issue.severity is Severity.WARNING for issue in self.issues)


@dataclass(frozen=True, slots=True)
class CandleValidationPolicy:
    """Explicit assumptions used when checking normalized candles."""

    anomalous_return_threshold: Decimal = Decimal("0.50")
    zero_volume_is_error: bool = False


class CandleValidator:
    """Validate chronology, completeness, schema invariants and anomalies."""

    def __init__(self, policy: CandleValidationPolicy | None = None) -> None:
        self.policy = policy or CandleValidationPolicy()

    def validate(
        self,
        candles: tuple[Candle, ...],
        *,
        as_of: datetime,
        expected_start: datetime | None = None,
        expected_end: datetime | None = None,
    ) -> ValidationReport:
        """Validate a homogeneous chronological candle batch as known at ``as_of``."""
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        cutoff = as_of.astimezone(UTC)
        issues: list[DataIssue] = []
        if not candles:
            issues.append(DataIssue("EMPTY_DATASET", Severity.ERROR, "dataset has no candles"))
            return ValidationReport(tuple(issues), 0)

        expected_symbol = candles[0].symbol
        expected_timeframe = candles[0].timeframe
        if expected_start is not None and candles[0].open_time != expected_start.astimezone(UTC):
            issues.append(
                DataIssue(
                    "MISSING_INITIAL_CANDLES",
                    Severity.ERROR,
                    f"expected first candle at {expected_start.astimezone(UTC).isoformat()}",
                    expected_symbol,
                    candles[0].open_time,
                )
            )
        if expected_end is not None and candles[-1].close_time != expected_end.astimezone(UTC):
            issues.append(
                DataIssue(
                    "MISSING_FINAL_CANDLES",
                    Severity.ERROR,
                    f"expected final close at {expected_end.astimezone(UTC).isoformat()}",
                    expected_symbol,
                    candles[-1].open_time,
                )
            )
        seen: set[datetime] = set()
        previous: Candle | None = None

        for candle in candles:

            def add(
                code: str,
                severity: Severity,
                message: str,
                current: Candle = candle,
            ) -> None:
                issues.append(DataIssue(code, severity, message, current.symbol, current.open_time))

            if candle.symbol != expected_symbol or candle.timeframe != expected_timeframe:
                add("MIXED_SERIES", Severity.ERROR, "batch mixes symbols or timeframes")
            if candle.open_time.tzinfo is None or candle.open_time.utcoffset() is None:
                add("NAIVE_TIMESTAMP", Severity.ERROR, "open_time has no timezone")
                previous = None
                continue
            offset = candle.open_time.utcoffset()
            if offset is None or offset.total_seconds() != 0:
                add("NON_UTC_TIMESTAMP", Severity.ERROR, "open_time is not represented in UTC")
            epoch_minutes = int(candle.open_time.timestamp()) // 60
            if (
                epoch_minutes % candle.timeframe.minutes != 0
                or candle.open_time.second
                or candle.open_time.microsecond
            ):
                add("MISALIGNED_TIMESTAMP", Severity.ERROR, "open_time is not aligned to timeframe")
            if candle.open_time in seen:
                add("DUPLICATE_TIMESTAMP", Severity.ERROR, "duplicate candle timestamp")
            seen.add(candle.open_time)
            if candle.close_time > cutoff:
                add("INCOMPLETE_CANDLE", Severity.ERROR, "candle was not closed at validation time")

            prices = (candle.open, candle.high, candle.low, candle.close)
            if any(price <= 0 for price in prices):
                add("NON_POSITIVE_PRICE", Severity.ERROR, "OHLC price is not positive")
            if candle.high < max(candle.open, candle.low, candle.close) or candle.low > min(
                candle.open, candle.high, candle.close
            ):
                add("INVALID_OHLC", Severity.ERROR, "high/low do not contain open and close")
            if candle.volume < 0 or candle.turnover < 0:
                add("NEGATIVE_ACTIVITY", Severity.ERROR, "volume or turnover is negative")
            if candle.volume == 0:
                severity = Severity.ERROR if self.policy.zero_volume_is_error else Severity.WARNING
                add("ZERO_VOLUME", severity, "candle has zero volume")

            if previous is not None:
                expected = previous.open_time + expected_timeframe.duration
                if candle.open_time <= previous.open_time:
                    add(
                        "NON_MONOTONIC_TIME",
                        Severity.ERROR,
                        "candles are not strictly chronological",
                    )
                elif candle.open_time != expected:
                    add(
                        "MISSING_CANDLES",
                        Severity.ERROR,
                        f"expected next candle at {expected.isoformat()}",
                    )
                if previous.close > 0:
                    absolute_return = abs(candle.close / previous.close - Decimal(1))
                    if absolute_return > self.policy.anomalous_return_threshold:
                        add(
                            "ANOMALOUS_RETURN",
                            Severity.WARNING,
                            f"absolute close return {absolute_return} exceeds threshold",
                        )
            previous = candle

        return ValidationReport(tuple(issues), len(candles))


class FundingValidator:
    """Validate a homogeneous settled funding series against its registered cadence."""

    def validate(
        self,
        rates: tuple[FundingRate, ...],
        *,
        interval_minutes: int,
        start: datetime,
        end: datetime,
        as_of: datetime,
    ) -> ValidationReport:
        """Require every settlement in the half-open UTC window exactly once."""
        for name, value in (("start", start), ("end", end), ("as_of", as_of)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if interval_minutes <= 0 or start >= end:
            raise ValueError("funding interval and window must be valid")
        issues: list[DataIssue] = []
        if not rates:
            return ValidationReport(
                (DataIssue("EMPTY_FUNDING", Severity.ERROR, "dataset has no funding rates"),), 0
            )
        expected_symbol = rates[0].symbol
        seen: set[datetime] = set()
        previous: FundingRate | None = None
        start_utc, end_utc, cutoff = (
            start.astimezone(UTC),
            end.astimezone(UTC),
            as_of.astimezone(UTC),
        )
        interval_seconds = interval_minutes * 60
        start_seconds = int(start_utc.timestamp())
        first_seconds = (
            (start_seconds + interval_seconds - 1) // interval_seconds
        ) * interval_seconds
        last_seconds = ((int(end_utc.timestamp()) - 1) // interval_seconds) * interval_seconds
        expected_first = datetime.fromtimestamp(first_seconds, tz=UTC)
        expected_last = datetime.fromtimestamp(last_seconds, tz=UTC)
        if rates[0].timestamp != expected_first:
            issues.append(
                DataIssue(
                    "MISSING_INITIAL_FUNDING",
                    Severity.ERROR,
                    f"expected first settlement at {expected_first.isoformat()}",
                    expected_symbol,
                    rates[0].timestamp,
                )
            )
        if rates[-1].timestamp != expected_last:
            issues.append(
                DataIssue(
                    "MISSING_FINAL_FUNDING",
                    Severity.ERROR,
                    f"expected final settlement at {expected_last.isoformat()}",
                    expected_symbol,
                    rates[-1].timestamp,
                )
            )
        for item in rates:

            def add(code: str, message: str, current: FundingRate = item) -> None:
                issues.append(
                    DataIssue(code, Severity.ERROR, message, current.symbol, current.timestamp)
                )

            if item.symbol != expected_symbol:
                add("MIXED_FUNDING_SERIES", "batch mixes funding symbols")
            if item.timestamp.tzinfo is None or item.timestamp.utcoffset() is None:
                add("NAIVE_FUNDING_TIMESTAMP", "funding timestamp has no timezone")
                previous = None
                continue
            offset = item.timestamp.utcoffset()
            if offset is None or offset.total_seconds() != 0:
                add("NON_UTC_FUNDING_TIMESTAMP", "funding timestamp is not represented in UTC")
            epoch_minutes = int(item.timestamp.timestamp()) // 60
            if (
                epoch_minutes % interval_minutes
                or item.timestamp.second
                or item.timestamp.microsecond
            ):
                add("MISALIGNED_FUNDING", "settlement is not aligned to the funding interval")
            if item.timestamp in seen:
                add("DUPLICATE_FUNDING", "duplicate funding settlement timestamp")
            seen.add(item.timestamp)
            if not start_utc <= item.timestamp < end_utc:
                add("OUTSIDE_FUNDING_WINDOW", "settlement is outside the requested window")
            if item.timestamp > cutoff:
                add("UNSETTLED_FUNDING", "funding timestamp is later than provider time")
            if not item.rate.is_finite():
                add("INVALID_FUNDING_RATE", "funding rate is not finite")
            if previous is not None:
                expected = previous.timestamp + timedelta(minutes=interval_minutes)
                if item.timestamp <= previous.timestamp:
                    add("NON_MONOTONIC_FUNDING", "funding timestamps are not chronological")
                elif item.timestamp != expected:
                    add("MISSING_FUNDING", f"expected settlement at {expected.isoformat()}")
            previous = item
        return ValidationReport(tuple(issues), len(rates))


class MarkPriceValidator:
    """Apply the candle integrity policy to OHLC-only mark-price bars."""

    def validate(
        self,
        candles: tuple[MarkPriceCandle, ...],
        *,
        as_of: datetime,
        expected_start: datetime | None = None,
        expected_end: datetime | None = None,
    ) -> ValidationReport:
        """Validate chronology, completeness, UTC alignment and OHLC invariants."""
        proxy = tuple(
            Candle(
                symbol=item.symbol,
                timeframe=item.timeframe,
                open_time=item.open_time,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=Decimal(1),
                turnover=Decimal(1),
                source=item.source,
            )
            for item in candles
        )
        return CandleValidator().validate(
            proxy,
            as_of=as_of,
            expected_start=expected_start,
            expected_end=expected_end,
        )
