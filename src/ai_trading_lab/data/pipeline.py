"""Orchestration from public provider responses to versioned curated datasets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ai_trading_lab.data.contracts import (
    CandleDownload,
    DataZone,
    InstrumentDownload,
    Timeframe,
)
from ai_trading_lab.data.manifest import Artifact, DatasetManifest, candle_dataset_version, utc_iso
from ai_trading_lab.data.storage import DataLake
from ai_trading_lab.data.validation import CandleValidator, ValidationReport


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """User-facing outcome of one immutable ingestion run."""

    dataset_version: str
    status: str
    row_count: int
    validation_errors: int
    validation_warnings: int
    manifest_path: Path


class MarketDataProvider(Protocol):
    """Provider boundary consumed by the exchange-independent pipeline."""

    def fetch_closed_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
        limit: int = 1_000,
    ) -> CandleDownload:
        """Return normalized closed candles and their raw evidence."""

    def fetch_instruments(self, symbols: frozenset[str] | None = None) -> InstrumentDownload:
        """Return normalized instruments and their raw evidence."""


class DataIngestionService:
    """Persist raw evidence before normalization, validation and curation."""

    def __init__(
        self,
        client: MarketDataProvider,
        lake: DataLake,
        validator: CandleValidator | None = None,
    ) -> None:
        self.client = client
        self.lake = lake
        self.validator = validator or CandleValidator()

    def ingest_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
    ) -> IngestionResult:
        """Ingest a closed candle window and quarantine any invalid normalized batch."""
        download = self.client.fetch_closed_candles(symbol, timeframe, start=start, end=end)
        raw_artifacts = tuple(self.lake.write_raw_page(page) for page in download.raw_pages)
        identity = (
            f"{symbol.upper()}|{timeframe.value}|{utc_iso(start)}|{utc_iso(end)}|"
            f"{self.validator.policy!r}"
        )
        version = candle_dataset_version(
            download.candles,
            transformation="bybit-v5-normalize-v1",
            identity=identity,
        )
        normalized = self.lake.write_candles(
            DataZone.NORMALIZED, download.candles, dataset_version=version
        )
        report = self.validator.validate(download.candles, as_of=download.server_time)
        artifacts = raw_artifacts + normalized
        if report.is_valid:
            status = "CURATED"
            artifacts += self.lake.write_candles(
                DataZone.CURATED, download.candles, dataset_version=version
            )
        else:
            status = "QUARANTINED"
            artifacts += self.lake.write_candles(
                DataZone.QUARANTINE, download.candles, dataset_version=version
            )
            artifacts += (self.lake.write_validation_report(version, report),)
        manifest = _candle_manifest(
            version=version,
            symbol=symbol.upper(),
            timeframe=timeframe,
            start=start,
            end=end,
            generated_at=download.raw_pages[0].retrieved_at,
            status=status,
            artifacts=artifacts,
            report=report,
        )
        path = self.lake.write_manifest(manifest)
        return IngestionResult(
            version,
            status,
            len(download.candles),
            report.error_count,
            report.warning_count,
            path,
        )

    def ingest_instruments(self, symbols: frozenset[str] | None = None) -> IngestionResult:
        """Ingest a curated snapshot of current USDT perpetual instrument constraints."""
        download = self.client.fetch_instruments(symbols)
        raw_artifacts = tuple(self.lake.write_raw_page(page) for page in download.raw_pages)
        digest = hashlib.sha256()
        for instrument in download.instruments:
            digest.update(repr(instrument).encode())
        version = f"DS-{digest.hexdigest()[:20].upper()}"
        curated = self.lake.write_instruments(download.instruments, dataset_version=version)
        generated_at = download.raw_pages[0].retrieved_at
        manifest = DatasetManifest(
            dataset_version=version,
            dataset_type="instrument_metadata_v1",
            provider="bybit_v5",
            category="linear",
            symbols=tuple(item.symbol for item in download.instruments),
            timeframes=(),
            start=None,
            end=None,
            generated_at=generated_at.astimezone(UTC).isoformat(),
            status="CURATED",
            transformation="bybit-v5-instruments-v1",
            parent_versions=(),
            artifacts=(*raw_artifacts, curated),
            row_count=len(download.instruments),
            validation_errors=0,
            validation_warnings=0,
        )
        path = self.lake.write_manifest(manifest)
        return IngestionResult(version, "CURATED", len(download.instruments), 0, 0, path)


def _candle_manifest(
    *,
    version: str,
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    generated_at: datetime,
    status: str,
    artifacts: tuple[Artifact, ...],
    report: ValidationReport,
) -> DatasetManifest:
    return DatasetManifest(
        dataset_version=version,
        dataset_type="ohlcv_v1",
        provider="bybit_v5",
        category="linear",
        symbols=(symbol,),
        timeframes=(timeframe.value,),
        start=utc_iso(start),
        end=utc_iso(end),
        generated_at=utc_iso(generated_at) or "",
        status=status,
        transformation="bybit-v5-normalize-v1",
        parent_versions=(),
        artifacts=artifacts,
        row_count=report.row_count,
        validation_errors=report.error_count,
        validation_warnings=report.warning_count,
    )
