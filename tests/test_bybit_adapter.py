"""Contract tests for the credential-free official Bybit V5 adapter."""

import json
import urllib.error
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import pytest

from ai_trading_lab.data.adapters.bybit_v5 import (
    INSTRUMENT_ENDPOINT,
    KLINE_ENDPOINT,
    SERVER_TIME_ENDPOINT,
    BybitAPIError,
    BybitV5PublicClient,
    UrlLibPublicTransport,
)
from ai_trading_lab.data.contracts import Timeframe

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


class FakeTransport:
    def __init__(self, responses: dict[str, list[dict[str, object]]]) -> None:
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls: dict[str, list[dict[str, str | int]]] = defaultdict(list)

    def get(self, endpoint: str, parameters: Any) -> dict[str, object]:
        self.calls[endpoint].append(dict(parameters))
        return self.responses[endpoint].pop(0)


def envelope(result: dict[str, object], *, code: int = 0) -> dict[str, object]:
    return {"retCode": code, "retMsg": "OK" if code == 0 else "failed", "result": result}


def instrument(symbol: str = "BTCUSDT", **changes: object) -> dict[str, object]:
    item: dict[str, object] = {
        "symbol": symbol,
        "baseCoin": symbol.removesuffix("USDT"),
        "quoteCoin": "USDT",
        "settleCoin": "USDT",
        "status": "Trading",
        "contractType": "LinearPerpetual",
        "launchTime": "1704067200000",
        "deliveryTime": "0",
        "priceFilter": {"tickSize": "0.10", "minPrice": "0.10", "maxPrice": "1000000"},
        "lotSizeFilter": {
            "qtyStep": "0.001",
            "minOrderQty": "0.001",
            "maxOrderQty": "100",
            "minNotionalValue": "5",
        },
        "leverageFilter": {"minLeverage": "1", "maxLeverage": "100", "leverageStep": "0.01"},
        "fundingInterval": 480,
    }
    item.update(changes)
    return item


def kline(minute: int, close: str = "101") -> list[str]:
    timestamp = int(datetime(2026, 1, 1, 0, minute, tzinfo=UTC).timestamp() * 1_000)
    return [str(timestamp), "100", "102", "99", close, "10", "1005"]


def test_server_time_preserves_raw_evidence() -> None:
    transport = FakeTransport({SERVER_TIME_ENDPOINT: [envelope({"timeSecond": "1767225780"})]})
    timestamp, page = BybitV5PublicClient(transport, clock=lambda: NOW).server_time()
    assert timestamp == datetime(2026, 1, 1, 0, 3, tzinfo=UTC)
    assert page.endpoint == SERVER_TIME_ENDPOINT
    assert page.retrieved_at == NOW


def test_instrument_pagination_filters_to_usdt_perpetuals() -> None:
    first = envelope(
        {
            "list": [instrument(), instrument("ETHUSDT", settleCoin="USDC")],
            "nextPageCursor": "next",
        }
    )
    second = envelope(
        {
            "list": [instrument("SOLUSDT"), instrument("XRPUSDT", status="PreLaunch")],
            "nextPageCursor": "",
        }
    )
    transport = FakeTransport({INSTRUMENT_ENDPOINT: [first, second]})
    result = BybitV5PublicClient(transport, clock=lambda: NOW).fetch_instruments(
        frozenset({"btcusdt", "solusdt"})
    )
    assert [item.symbol for item in result.instruments] == ["BTCUSDT", "SOLUSDT"]
    assert result.instruments[0].delivery_time is None
    assert result.instruments[0].funding_interval_minutes == 480
    assert transport.calls[INSTRUMENT_ENDPOINT][1]["cursor"] == "next"
    assert len(result.raw_pages) == 2


def test_repeated_instrument_cursor_is_rejected() -> None:
    page = envelope({"list": [], "nextPageCursor": "same"})
    transport = FakeTransport({INSTRUMENT_ENDPOINT: [page, page]})
    with pytest.raises(BybitAPIError, match="did not advance"):
        BybitV5PublicClient(transport, clock=lambda: NOW).fetch_instruments()


def test_missing_requested_instrument_is_rejected() -> None:
    page = envelope({"list": [instrument()], "nextPageCursor": ""})
    transport = FakeTransport({INSTRUMENT_ENDPOINT: [page]})
    with pytest.raises(BybitAPIError, match="not found: ETHUSDT"):
        BybitV5PublicClient(transport, clock=lambda: NOW).fetch_instruments(
            frozenset({"BTCUSDT", "ETHUSDT"})
        )


def test_closed_candles_paginate_backward_sort_and_drop_incomplete() -> None:
    transport = FakeTransport(
        {
            SERVER_TIME_ENDPOINT: [envelope({"timeSecond": "1767225780"})],
            KLINE_ENDPOINT: [
                envelope({"list": [kline(3), kline(2)]}),
                envelope({"list": [kline(1), kline(0)]}),
            ],
        }
    )
    result = BybitV5PublicClient(transport, clock=lambda: NOW).fetch_closed_candles(
        "btcusdt",
        Timeframe.ONE_MINUTE,
        start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        end=datetime(2026, 1, 1, 0, 4, tzinfo=UTC),
        limit=2,
    )
    assert [item.open_time.minute for item in result.candles] == [0, 1, 2]
    assert result.candles[0].symbol == "BTCUSDT"
    assert len(result.raw_pages) == 3
    assert transport.calls[KLINE_ENDPOINT][1]["end"] < transport.calls[KLINE_ENDPOINT][0]["end"]


def test_provider_duplicates_are_preserved_for_validator() -> None:
    transport = FakeTransport(
        {
            SERVER_TIME_ENDPOINT: [envelope({"timeSecond": "1767225780"})],
            KLINE_ENDPOINT: [envelope({"list": [kline(0), kline(0)]})],
        }
    )
    result = BybitV5PublicClient(transport, clock=lambda: NOW).fetch_closed_candles(
        "BTCUSDT",
        Timeframe.ONE_MINUTE,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )
    assert len(result.candles) == 2
    assert result.candles[0].open_time == result.candles[1].open_time


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start": NOW, "end": NOW}, "start must"),
        (
            {"start": datetime(2026, 1, 1, tzinfo=UTC), "end": NOW, "limit": 0},
            "limit",
        ),
    ],
)
def test_candle_request_validation(kwargs: dict[str, object], message: str) -> None:
    client = BybitV5PublicClient(FakeTransport({}), clock=lambda: NOW)
    with pytest.raises(ValueError, match=message):
        client.fetch_closed_candles("BTCUSDT", Timeframe.ONE_MINUTE, **kwargs)  # type: ignore[arg-type]


def test_invalid_symbol_and_clock_are_rejected() -> None:
    client = BybitV5PublicClient(FakeTransport({}), clock=lambda: NOW)
    with pytest.raises(ValueError, match="symbol"):
        client.fetch_closed_candles(
            "bad symbol",
            Timeframe.ONE_MINUTE,
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=NOW,
        )
    naive_clock = BybitV5PublicClient(
        FakeTransport({SERVER_TIME_ENDPOINT: [envelope({"timeSecond": "1"})]}),
        clock=lambda: datetime(2026, 1, 1),
    )
    with pytest.raises(ValueError, match="clock"):
        naive_clock.server_time()


def test_bybit_error_and_invalid_rows_fail_closed() -> None:
    error = FakeTransport({SERVER_TIME_ENDPOINT: [envelope({}, code=10006)]})
    preserved = []
    with pytest.raises(BybitAPIError, match="retCode"):
        BybitV5PublicClient(error, clock=lambda: NOW, raw_page_sink=preserved.append).server_time()
    assert preserved[0].payload["retCode"] == 10006

    invalid = FakeTransport(
        {
            SERVER_TIME_ENDPOINT: [envelope({"timeSecond": "1767226000"})],
            KLINE_ENDPOINT: [envelope({"list": [["bad"]]})],
        }
    )
    with pytest.raises(BybitAPIError, match="seven string"):
        BybitV5PublicClient(invalid, clock=lambda: NOW).fetch_closed_candles(
            "BTCUSDT",
            Timeframe.ONE_MINUTE,
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
        )


def test_transport_restricts_host_and_decodes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="official"):
        UrlLibPublicTransport(base_url="https://example.com")
    with pytest.raises(ValueError, match="timeout"):
        UrlLibPublicTransport(timeout_seconds=0)

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(envelope({"timeSecond": "1"})).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    result = UrlLibPublicTransport().get(SERVER_TIME_ENDPOINT, {})
    assert result["retCode"] == 0


def test_transport_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    with pytest.raises(BybitAPIError, match="bounded retries"):
        UrlLibPublicTransport(attempts=2).get(SERVER_TIME_ENDPOINT, {})
