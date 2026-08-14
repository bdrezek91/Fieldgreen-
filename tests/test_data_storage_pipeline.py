"""Storage, manifest, quarantine and idempotency integration tests."""

import gzip
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from ai_trading_lab.data.contracts import (
    CandleDownload,
    DataZone,
    FundingDownload,
    FundingRate,
    Instrument,
    InstrumentDownload,
    MarkPriceCandle,
    MarkPriceDownload,
    RawPage,
    Timeframe,
)
from ai_trading_lab.data.loader import CuratedDataLoader, DatasetSelectionError
from ai_trading_lab.data.manifest import DatasetManifest, file_sha256
from ai_trading_lab.data.pipeline import DataIngestionService
from ai_trading_lab.data.storage import DataLake

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def raw_page(endpoint: str = "/v5/market/kline") -> RawPage:
    return RawPage(endpoint, {"category": "linear"}, {"retCode": 0, "result": {}}, NOW)


def make_instrument() -> Instrument:
    return Instrument(
        symbol="BTCUSDT",
        base_coin="BTC",
        quote_coin="USDT",
        settle_coin="USDT",
        status="Trading",
        contract_type="LinearPerpetual",
        launch_time=datetime(2020, 1, 1, tzinfo=UTC),
        delivery_time=None,
        tick_size=Decimal("0.10"),
        min_price=Decimal("0.10"),
        max_price=Decimal("1000000"),
        quantity_step=Decimal("0.001"),
        min_order_quantity=Decimal("0.001"),
        max_order_quantity=Decimal("100"),
        min_notional=Decimal("5"),
        min_leverage=Decimal("1"),
        max_leverage=Decimal("100"),
        leverage_step=Decimal("0.01"),
        funding_interval_minutes=480,
    )


class FakeClient:
    def __init__(self, candles, *, instruments=(), funding=(), marks=()) -> None:  # type: ignore[no-untyped-def]
        self.candles = tuple(candles)
        self.instruments = tuple(instruments)
        self.funding = tuple(funding)
        self.marks = tuple(marks)

    def fetch_closed_candles(self, *_args, **_kwargs) -> CandleDownload:  # type: ignore[no-untyped-def]
        return CandleDownload(self.candles, (raw_page(),), NOW)

    def fetch_instruments(self, _symbols=None) -> InstrumentDownload:  # type: ignore[no-untyped-def]
        return InstrumentDownload(self.instruments, (raw_page("/v5/market/instruments-info"),))

    def fetch_funding_rates(self, *_args, **_kwargs) -> FundingDownload:  # type: ignore[no-untyped-def]
        return FundingDownload(self.funding, (raw_page("/v5/market/funding/history"),), NOW)

    def fetch_mark_price_candles(self, *_args, **_kwargs) -> MarkPriceDownload:  # type: ignore[no-untyped-def]
        return MarkPriceDownload(self.marks, (raw_page("/v5/market/mark-price-kline"),), NOW)


def test_raw_storage_is_canonical_and_idempotent(tmp_path: Path) -> None:
    lake = DataLake(tmp_path)
    first = lake.write_raw_page(raw_page())
    target = tmp_path / first.relative_path
    first_mtime = target.stat().st_mtime_ns
    second = lake.write_raw_page(raw_page())
    assert first == second
    assert target.stat().st_mtime_ns == first_mtime
    document = json.loads(gzip.decompress(target.read_bytes()))
    assert document["payload"]["retCode"] == 0
    assert file_sha256(target) == first.sha256


def test_parquet_is_partitioned_and_exact(tmp_path: Path, candle_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (candle_factory(0), candle_factory(1))
    artifacts = DataLake(tmp_path).write_candles(
        DataZone.CURATED, candles, dataset_version="DS-TEST"
    )
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert "timeframe=1m/symbol=BTCUSDT/year=2026/month=01" in artifact.relative_path
    table = pq.read_table(tmp_path / artifact.relative_path)
    assert table.num_rows == 2
    assert table.column("close").to_pylist() == [Decimal("101.000000000000000000")] * 2
    with pytest.raises(ValueError, match="normalized"):
        DataLake(tmp_path).write_candles(DataZone.RAW, candles, dataset_version="DS-X")


def test_valid_pipeline_promotes_and_is_idempotent(tmp_path: Path, candle_factory) -> None:  # type: ignore[no-untyped-def]
    client = FakeClient((candle_factory(0), candle_factory(1)))
    service = DataIngestionService(client, DataLake(tmp_path))  # type: ignore[arg-type]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 2, tzinfo=UTC)
    first = service.ingest_candles("BTCUSDT", Timeframe.ONE_MINUTE, start=start, end=end)
    second = service.ingest_candles("BTCUSDT", Timeframe.ONE_MINUTE, start=start, end=end)
    assert first == second
    assert first.status == "CURATED"
    manifest = json.loads(first.manifest_path.read_text())
    assert manifest["row_count"] == 2
    assert {item["zone"] for item in manifest["artifacts"]} == {"raw", "normalized", "curated"}
    assert len(list(tmp_path.rglob("*.parquet"))) == 2
    loaded = CuratedDataLoader(tmp_path).candles(first.dataset_version)
    assert loaded == client.candles
    assert (
        CuratedDataLoader(tmp_path).resolve_unique(
            dataset_type="ohlcv_v1",
            symbol="BTCUSDT",
            timeframe="1m",
            start=start.isoformat(),
            end=end.isoformat(),
        )
        == first.dataset_version
    )


def test_invalid_pipeline_quarantines_without_curated_data(tmp_path: Path, candle_factory) -> None:  # type: ignore[no-untyped-def]
    client = FakeClient((candle_factory(0), candle_factory(2)))
    service = DataIngestionService(client, DataLake(tmp_path))  # type: ignore[arg-type]
    result = service.ingest_candles(
        "BTCUSDT",
        Timeframe.ONE_MINUTE,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    assert result.status == "QUARANTINED"
    assert result.validation_errors == 1
    manifest = json.loads(result.manifest_path.read_text())
    zones = {item["zone"] for item in manifest["artifacts"]}
    assert zones == {"raw", "normalized", "quarantine"}
    report_path = next(tmp_path.glob("quarantine/reports/*.json"))
    assert json.loads(report_path.read_text())["issues"][0]["code"] == "MISSING_CANDLES"
    assert not (tmp_path / "curated").exists()


def test_instrument_pipeline_writes_snapshot_and_manifest(tmp_path: Path) -> None:
    service = DataIngestionService(  # type: ignore[arg-type]
        FakeClient((), instruments=(make_instrument(),)), DataLake(tmp_path)
    )
    result = service.ingest_instruments(frozenset({"BTCUSDT"}))
    assert result.status == "CURATED"
    assert result.row_count == 1
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["dataset_type"] == "instrument_metadata_v1"
    parquet = next(tmp_path.glob("curated/bybit/linear/instruments/*.parquet"))
    assert pq.read_table(parquet).column("symbol").to_pylist() == ["BTCUSDT"]
    assert CuratedDataLoader(tmp_path).instruments(result.dataset_version) == (make_instrument(),)


def test_funding_pipeline_curates_complete_history(tmp_path: Path) -> None:
    rates = tuple(
        FundingRate(
            "BTCUSDT",
            datetime(2026, 1, 1, hour, tzinfo=UTC),
            Decimal("0.0001"),
        )
        for hour in (0, 8, 16)
    )
    service = DataIngestionService(FakeClient((), funding=rates), DataLake(tmp_path))  # type: ignore[arg-type]
    result = service.ingest_funding(
        "BTCUSDT",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        interval_minutes=480,
    )
    assert result.status == "CURATED"
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["dataset_type"] == "funding_v1"
    assert manifest["row_count"] == 3
    parquet = next(tmp_path.glob("curated/bybit/linear/funding/**/*.parquet"))
    assert pq.read_table(parquet).column("rate").to_pylist()[0] == Decimal("0.000100000000000000")
    assert CuratedDataLoader(tmp_path).funding(result.dataset_version) == rates


def test_funding_pipeline_quarantines_incomplete_history(tmp_path: Path) -> None:
    rates = (FundingRate("BTCUSDT", datetime(2026, 1, 1, 8, tzinfo=UTC), Decimal("0.0001")),)
    service = DataIngestionService(FakeClient((), funding=rates), DataLake(tmp_path))  # type: ignore[arg-type]
    result = service.ingest_funding(
        "BTCUSDT",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        interval_minutes=480,
    )
    assert result.status == "QUARANTINED"
    assert result.validation_errors == 2
    assert not list(tmp_path.glob("curated/bybit/linear/funding/**/*.parquet"))


def test_mark_price_pipeline_curates_complete_bars(tmp_path: Path) -> None:
    marks = tuple(
        MarkPriceCandle(
            "BTCUSDT",
            Timeframe.ONE_HOUR,
            datetime(2026, 1, 1, hour, tzinfo=UTC),
            Decimal("100"),
            Decimal("102"),
            Decimal("99"),
            Decimal("101"),
        )
        for hour in (0, 1, 2)
    )
    service = DataIngestionService(FakeClient((), marks=marks), DataLake(tmp_path))  # type: ignore[arg-type]
    result = service.ingest_mark_prices(
        "BTCUSDT",
        Timeframe.ONE_HOUR,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, 3, tzinfo=UTC),
    )
    assert result.status == "CURATED"
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["dataset_type"] == "mark_price_ohlc_v1"
    assert list(tmp_path.glob("curated/bybit/linear/mark_price/**/*.parquet"))
    assert CuratedDataLoader(tmp_path).mark_prices(result.dataset_version) == marks


def test_curated_loader_rejects_missing_or_corrupt_evidence(tmp_path: Path) -> None:
    loader = CuratedDataLoader(tmp_path)
    with pytest.raises(DatasetSelectionError, match="does not exist"):
        loader.candles("DS-MISSING")
    with pytest.raises(DatasetSelectionError, match="found 0"):
        loader.resolve_unique(
            dataset_type="ohlcv_v1",
            symbol="BTCUSDT",
            timeframe="1h",
            start=NOW.isoformat(),
            end=NOW.isoformat(),
        )


def test_curated_loader_rejects_wrong_type_and_corrupt_parquet(
    tmp_path: Path, candle_factory
) -> None:  # type: ignore[no-untyped-def]
    service = DataIngestionService(FakeClient((candle_factory(),)), DataLake(tmp_path))  # type: ignore[arg-type]
    result = service.ingest_candles(
        "BTCUSDT",
        Timeframe.ONE_MINUTE,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )
    assert result.status == "CURATED"
    loader = CuratedDataLoader(tmp_path)
    with pytest.raises(DatasetSelectionError, match="curated funding_v1"):
        loader.funding(result.dataset_version)

    parquet = next(tmp_path.glob("curated/bybit/linear/ohlcv/**/*.parquet"))
    parquet.write_bytes(b"corrupt")
    with pytest.raises(DatasetSelectionError, match="missing or corrupt"):
        loader.candles(result.dataset_version)


def test_curated_loader_rejects_non_object_manifest(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "ds-list.json").write_text("[]", encoding="utf-8")
    with pytest.raises(DatasetSelectionError, match="JSON object"):
        CuratedDataLoader(tmp_path).candles("DS-LIST")


def test_manifest_write_once_and_empty_candle_write(tmp_path: Path) -> None:
    lake = DataLake(tmp_path)
    assert lake.write_candles(DataZone.CURATED, (), dataset_version="DS-EMPTY") == ()
    manifest = DatasetManifest(
        "DS-EMPTY",
        "ohlcv_v1",
        "bybit_v5",
        "linear",
        ("BTCUSDT",),
        ("1m",),
        None,
        None,
        NOW.isoformat(),
        "QUARANTINED",
        "test",
        (),
        (),
        0,
        1,
        0,
    )
    target = lake.write_manifest(manifest)
    initial = target.read_bytes()
    lake.write_manifest(manifest)
    assert target.read_bytes() == initial
    with pytest.raises(ValueError, match="funding Parquet"):
        lake.write_funding_rates(DataZone.RAW, (), dataset_version="DS-X")
    with pytest.raises(ValueError, match="mark-price Parquet"):
        lake.write_mark_price_candles(DataZone.RAW, (), dataset_version="DS-X")
