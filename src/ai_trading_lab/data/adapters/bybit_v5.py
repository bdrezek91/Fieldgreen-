"""Credential-free adapter for official Bybit V5 public market endpoints."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, Protocol, cast

from ai_trading_lab.data.contracts import (
    BYBIT_CATEGORY,
    BYBIT_SETTLE_COIN,
    Candle,
    CandleDownload,
    Instrument,
    InstrumentDownload,
    RawPage,
    Timeframe,
    milliseconds,
    utc_from_milliseconds,
)

PRODUCTION_BASE_URL: Final = "https://api.bybit.com"
KLINE_ENDPOINT: Final = "/v5/market/kline"
INSTRUMENT_ENDPOINT: Final = "/v5/market/instruments-info"
SERVER_TIME_ENDPOINT: Final = "/v5/market/time"


class BybitAPIError(RuntimeError):
    """Raised when transport or Bybit's response envelope is invalid."""


class PublicTransport(Protocol):
    """Minimal injectable transport required by the public adapter."""

    def get(self, endpoint: str, parameters: Mapping[str, str | int]) -> dict[str, object]:
        """Fetch and decode one public JSON response."""


class UrlLibPublicTransport:
    """Small dependency-free HTTPS transport with bounded retries and no credentials."""

    def __init__(
        self,
        *,
        base_url: str = PRODUCTION_BASE_URL,
        timeout_seconds: float = 20.0,
        attempts: int = 3,
    ) -> None:
        if base_url != PRODUCTION_BASE_URL:
            raise ValueError("PHASE 2 transport permits only the official Bybit production host")
        if timeout_seconds <= 0 or attempts < 1:
            raise ValueError("timeout must be positive and attempts must be at least one")
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.attempts = attempts

    def get(self, endpoint: str, parameters: Mapping[str, str | int]) -> dict[str, object]:
        """Perform a public GET request and return its decoded object payload."""
        query = urllib.parse.urlencode(parameters)
        request = urllib.request.Request(
            f"{self.base_url}{endpoint}?{query}" if query else f"{self.base_url}{endpoint}",
            headers={"Accept": "application/json", "User-Agent": "ai-trading-lab/0.3.0"},
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                # Host is fixed to the official HTTPS endpoint in __init__.
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                    payload = json.loads(response.read())
                if not isinstance(payload, dict):
                    raise BybitAPIError("Bybit returned a non-object JSON payload")
                return cast(dict[str, object], payload)
            except (OSError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.25 * (2**attempt))
        raise BybitAPIError("Bybit public request failed after bounded retries") from last_error


class BybitV5PublicClient:
    """Normalize Bybit V5 public data into domain-owned contracts."""

    def __init__(
        self,
        transport: PublicTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        raw_page_sink: Callable[[RawPage], object] | None = None,
    ) -> None:
        self.transport = transport or UrlLibPublicTransport()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.raw_page_sink = raw_page_sink

    def server_time(self) -> tuple[datetime, RawPage]:
        """Read Bybit server time, preserving the raw response."""
        retrieved_at = self._now()
        payload = self.transport.get(SERVER_TIME_ENDPOINT, {})
        page = RawPage(SERVER_TIME_ENDPOINT, {}, payload, retrieved_at)
        self._preserve(page)
        result = _result(payload)
        seconds = _required_string(result, "timeSecond")
        timestamp = datetime.fromtimestamp(int(seconds), tz=UTC)
        return timestamp, page

    def fetch_instruments(self, symbols: frozenset[str] | None = None) -> InstrumentDownload:
        """Fetch every trading linear USDT perpetual, following Bybit cursors."""
        cursor = ""
        instruments: list[Instrument] = []
        pages: list[RawPage] = []
        seen_cursors: set[str] = set()
        wanted = frozenset(symbol.upper() for symbol in symbols) if symbols else None

        while True:
            parameters: dict[str, str | int] = {"category": BYBIT_CATEGORY, "limit": 1_000}
            if cursor:
                parameters["cursor"] = cursor
            retrieved_at = self._now()
            payload = self.transport.get(INSTRUMENT_ENDPOINT, parameters)
            page = RawPage(INSTRUMENT_ENDPOINT, parameters, payload, retrieved_at)
            self._preserve(page)
            result = _result(payload)
            if result.get("category") not in {None, BYBIT_CATEGORY}:
                raise BybitAPIError("instrument response category does not match linear")
            pages.append(page)
            for raw in _required_list(result, "list"):
                item = _object(raw, "instrument")
                if (
                    _required_string(item, "settleCoin") != BYBIT_SETTLE_COIN
                    or _required_string(item, "contractType") != "LinearPerpetual"
                    or _required_string(item, "status") != "Trading"
                ):
                    continue
                symbol = _required_string(item, "symbol")
                if wanted is None or symbol in wanted:
                    instruments.append(_parse_instrument(item))

            next_cursor = result.get("nextPageCursor", "")
            if not isinstance(next_cursor, str):
                raise BybitAPIError("nextPageCursor must be a string")
            if not next_cursor:
                break
            if next_cursor in seen_cursors:
                raise BybitAPIError("instrument pagination cursor did not advance")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        if wanted is not None:
            missing = wanted - {item.symbol for item in instruments}
            if missing:
                raise BybitAPIError(
                    f"requested instruments not found: {', '.join(sorted(missing))}"
                )
        if not instruments:
            raise BybitAPIError("Bybit returned no eligible USDT perpetual instruments")
        return InstrumentDownload(
            tuple(sorted(instruments, key=lambda item: item.symbol)), tuple(pages)
        )

    def fetch_closed_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
        limit: int = 1_000,
    ) -> CandleDownload:
        """Backfill closed candles in ``[start, end)`` using backward pagination."""
        start_ms = milliseconds(start)
        end_ms = milliseconds(end)
        if start_ms >= end_ms:
            raise ValueError("start must be earlier than end")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or not normalized_symbol.isalnum():
            raise ValueError("symbol must be a non-empty uppercase-compatible token")

        server_time, time_page = self.server_time()
        pages: list[RawPage] = [time_page]
        candles: list[Candle] = []
        page_end = end_ms - 1

        while page_end >= start_ms:
            parameters: dict[str, str | int] = {
                "category": BYBIT_CATEGORY,
                "symbol": normalized_symbol,
                "interval": timeframe.bybit_code,
                "start": start_ms,
                "end": page_end,
                "limit": limit,
            }
            retrieved_at = self._now()
            payload = self.transport.get(KLINE_ENDPOINT, parameters)
            page = RawPage(KLINE_ENDPOINT, parameters, payload, retrieved_at)
            self._preserve(page)
            result = _result(payload)
            if result.get("category") not in {None, BYBIT_CATEGORY}:
                raise BybitAPIError("kline response category does not match linear")
            if result.get("symbol") not in {None, normalized_symbol}:
                raise BybitAPIError("kline response symbol does not match request")
            pages.append(page)
            raw_rows = _required_list(result, "list")
            if not raw_rows:
                break
            parsed = tuple(_parse_candle(normalized_symbol, timeframe, row) for row in raw_rows)
            for candle in parsed:
                if (
                    start_ms <= milliseconds(candle.open_time) < end_ms
                    and candle.close_time <= server_time
                ):
                    candles.append(candle)
            oldest_ms = min(milliseconds(candle.open_time) for candle in parsed)
            if oldest_ms <= start_ms:
                break
            next_end = oldest_ms - 1
            if next_end >= page_end:
                raise BybitAPIError("kline pagination did not advance")
            page_end = next_end

        chronological = tuple(sorted(candles, key=lambda item: item.open_time))
        return CandleDownload(chronological, tuple(pages), server_time)

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("adapter clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    def _preserve(self, page: RawPage) -> None:
        if self.raw_page_sink is not None:
            self.raw_page_sink(page)


def _result(payload: Mapping[str, object]) -> dict[str, object]:
    code = payload.get("retCode")
    if code != 0:
        raise BybitAPIError(f"Bybit error retCode={code!r}, retMsg={payload.get('retMsg')!r}")
    return _object(payload.get("result"), "result")


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise BybitAPIError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _required_string(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str):
        raise BybitAPIError(f"{key} must be a string")
    return value


def _required_list(item: Mapping[str, object], key: str) -> list[object]:
    value = item.get(key)
    if not isinstance(value, list):
        raise BybitAPIError(f"{key} must be a list")
    return value


def _parse_candle(symbol: str, timeframe: Timeframe, raw: object) -> Candle:
    if (
        not isinstance(raw, list)
        or len(raw) < 7
        or not all(isinstance(value, str) for value in raw[:7])
    ):
        raise BybitAPIError("kline row must contain seven string fields")
    values = cast(list[str], raw)
    try:
        return Candle(
            symbol=symbol,
            timeframe=timeframe,
            open_time=utc_from_milliseconds(values[0]),
            open=Decimal(values[1]),
            high=Decimal(values[2]),
            low=Decimal(values[3]),
            close=Decimal(values[4]),
            volume=Decimal(values[5]),
            turnover=Decimal(values[6]),
        )
    except (ValueError, ArithmeticError) as exc:
        raise BybitAPIError("kline row contains an invalid numeric value") from exc


def _parse_instrument(item: Mapping[str, object]) -> Instrument:
    price = _object(item.get("priceFilter"), "priceFilter")
    lot = _object(item.get("lotSizeFilter"), "lotSizeFilter")
    leverage = _object(item.get("leverageFilter"), "leverageFilter")
    delivery_ms = _required_string(item, "deliveryTime")
    funding_interval = item.get("fundingInterval")
    if not isinstance(funding_interval, int):
        raise BybitAPIError("fundingInterval must be an integer")
    try:
        return Instrument(
            symbol=_required_string(item, "symbol"),
            base_coin=_required_string(item, "baseCoin"),
            quote_coin=_required_string(item, "quoteCoin"),
            settle_coin=_required_string(item, "settleCoin"),
            status=_required_string(item, "status"),
            contract_type=_required_string(item, "contractType"),
            launch_time=utc_from_milliseconds(_required_string(item, "launchTime")),
            delivery_time=utc_from_milliseconds(delivery_ms) if int(delivery_ms) > 0 else None,
            tick_size=Decimal(_required_string(price, "tickSize")),
            min_price=Decimal(_required_string(price, "minPrice")),
            max_price=Decimal(_required_string(price, "maxPrice")),
            quantity_step=Decimal(_required_string(lot, "qtyStep")),
            min_order_quantity=Decimal(_required_string(lot, "minOrderQty")),
            max_order_quantity=Decimal(_required_string(lot, "maxOrderQty")),
            min_notional=Decimal(_required_string(lot, "minNotionalValue")),
            min_leverage=Decimal(_required_string(leverage, "minLeverage")),
            max_leverage=Decimal(_required_string(leverage, "maxLeverage")),
            leverage_step=Decimal(_required_string(leverage, "leverageStep")),
            funding_interval_minutes=funding_interval,
        )
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise BybitAPIError("instrument contains an invalid numeric value") from exc
