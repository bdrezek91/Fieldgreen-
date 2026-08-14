"""Deterministic market-data integrity validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from ai_trading_lab.data.contracts import Candle


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

    def validate(self, candles: tuple[Candle, ...], *, as_of: datetime) -> ValidationReport:
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
