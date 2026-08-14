"""Framework-neutral market-data domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final

BYBIT_CATEGORY: Final = "linear"
BYBIT_SETTLE_COIN: Final = "USDT"
INITIAL_SYMBOLS: Final = frozenset(
    {
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "BNBUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "LINKUSDT",
        "AVAXUSDT",
        "BCHUSDT",
        "LTCUSDT",
    }
)


class Timeframe(StrEnum):
    """Canonical timeframes supported by the first data-engine release."""

    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"

    @property
    def duration(self) -> timedelta:
        """Return the exact fixed duration of this candle interval."""
        return timedelta(minutes=self.minutes)

    @property
    def minutes(self) -> int:
        """Return interval length in minutes."""
        return {
            Timeframe.ONE_MINUTE: 1,
            Timeframe.FIVE_MINUTES: 5,
            Timeframe.FIFTEEN_MINUTES: 15,
            Timeframe.ONE_HOUR: 60,
            Timeframe.FOUR_HOURS: 240,
            Timeframe.ONE_DAY: 1_440,
        }[self]

    @property
    def bybit_code(self) -> str:
        """Return the official Bybit V5 interval code."""
        return {
            Timeframe.ONE_MINUTE: "1",
            Timeframe.FIVE_MINUTES: "5",
            Timeframe.FIFTEEN_MINUTES: "15",
            Timeframe.ONE_HOUR: "60",
            Timeframe.FOUR_HOURS: "240",
            Timeframe.ONE_DAY: "D",
        }[self]


class DataZone(StrEnum):
    """Immutable data-lake zones with progressively stronger guarantees."""

    RAW = "raw"
    NORMALIZED = "normalized"
    CURATED = "curated"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class Candle:
    """A provider-independent OHLCV candle using exact decimal values and UTC."""

    symbol: str
    timeframe: Timeframe
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal
    source: str = "bybit_v5"

    @property
    def close_time(self) -> datetime:
        """Return the exclusive end timestamp of the candle."""
        return self.open_time + self.timeframe.duration


@dataclass(frozen=True, slots=True)
class Instrument:
    """Trading constraints for one linear USDT perpetual instrument."""

    symbol: str
    base_coin: str
    quote_coin: str
    settle_coin: str
    status: str
    contract_type: str
    launch_time: datetime
    delivery_time: datetime | None
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal
    quantity_step: Decimal
    min_order_quantity: Decimal
    max_order_quantity: Decimal
    min_notional: Decimal
    min_leverage: Decimal
    max_leverage: Decimal
    leverage_step: Decimal
    funding_interval_minutes: int
    source: str = "bybit_v5"


@dataclass(frozen=True, slots=True)
class RawPage:
    """One unmodified provider response with retrieval context."""

    endpoint: str
    parameters: dict[str, str | int]
    payload: dict[str, object]
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class CandleDownload:
    """Closed candles plus the raw pages from which they were normalized."""

    candles: tuple[Candle, ...]
    raw_pages: tuple[RawPage, ...]
    server_time: datetime


@dataclass(frozen=True, slots=True)
class InstrumentDownload:
    """Instrument metadata plus every raw pagination page."""

    instruments: tuple[Instrument, ...]
    raw_pages: tuple[RawPage, ...]


def utc_from_milliseconds(value: str | int) -> datetime:
    """Convert a Unix millisecond value to an aware UTC datetime."""
    return datetime.fromtimestamp(int(value) / 1_000, tz=UTC)


def milliseconds(value: datetime) -> int:
    """Convert an aware datetime to Unix milliseconds, rejecting naive inputs."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return int(value.astimezone(UTC).timestamp() * 1_000)
