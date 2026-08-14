"""Fail-closed reads of immutable curated Parquet evidence."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq

from ai_trading_lab.data.contracts import (
    Candle,
    FundingRate,
    Instrument,
    MarkPriceCandle,
    Timeframe,
)
from ai_trading_lab.data.manifest import file_sha256


class DatasetSelectionError(ValueError):
    """Raised when curated evidence is missing, ambiguous or corrupt."""


class CuratedDataLoader:
    """Resolve exact manifests and reconstruct owned domain contracts."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve_unique(
        self,
        *,
        dataset_type: str,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> str:
        """Resolve exactly one curated dataset matching all requested dimensions."""
        matches = []
        for path in sorted((self.root / "manifests").glob("ds-*.json")):
            document = _document(path)
            if (
                document.get("status") == "CURATED"
                and document.get("dataset_type") == dataset_type
                and document.get("symbols") == [symbol]
                and document.get("timeframes") == [timeframe]
                and document.get("start") == start
                and document.get("end") == end
            ):
                matches.append(str(document["dataset_version"]))
        if len(matches) != 1:
            raise DatasetSelectionError(
                f"expected one curated {dataset_type} dataset for {symbol}/{timeframe}; "
                f"found {len(matches)}"
            )
        return matches[0]

    def candles(self, version: str) -> tuple[Candle, ...]:
        """Load one curated OHLCV dataset and verify every artifact hash."""
        manifest = self._manifest(version, "ohlcv_v1")
        symbol = _single(manifest, "symbols")
        timeframe = Timeframe(_single(manifest, "timeframes"))
        return tuple(
            Candle(
                symbol,
                timeframe,
                cast(datetime, row["open_time"]),
                cast(Decimal, row["open"]),
                cast(Decimal, row["high"]),
                cast(Decimal, row["low"]),
                cast(Decimal, row["close"]),
                cast(Decimal, row["volume"]),
                cast(Decimal, row["turnover"]),
                str(row["source"]),
            )
            for row in self._rows(manifest)
        )

    def funding(self, version: str) -> tuple[FundingRate, ...]:
        """Load one curated funding dataset."""
        manifest = self._manifest(version, "funding_v1")
        symbol = _single(manifest, "symbols")
        return tuple(
            FundingRate(
                symbol,
                cast(datetime, row["timestamp"]),
                cast(Decimal, row["rate"]),
                str(row["source"]),
            )
            for row in self._rows(manifest)
        )

    def mark_prices(self, version: str) -> tuple[MarkPriceCandle, ...]:
        """Load one curated historical mark-price dataset."""
        manifest = self._manifest(version, "mark_price_ohlc_v1")
        symbol = _single(manifest, "symbols")
        timeframe = Timeframe(_single(manifest, "timeframes"))
        return tuple(
            MarkPriceCandle(
                symbol,
                timeframe,
                cast(datetime, row["open_time"]),
                cast(Decimal, row["open"]),
                cast(Decimal, row["high"]),
                cast(Decimal, row["low"]),
                cast(Decimal, row["close"]),
                str(row["source"]),
            )
            for row in self._rows(manifest)
        )

    def instruments(self, version: str) -> tuple[Instrument, ...]:
        """Load a curated instrument snapshot selected explicitly by version."""
        manifest = self._manifest(version, "instrument_metadata_v1")
        return tuple(Instrument(**row) for row in self._rows(manifest))

    def _manifest(self, version: str, expected_type: str) -> dict[str, Any]:
        path = self.root / "manifests" / f"{version.lower()}.json"
        document = _document(path)
        if document.get("dataset_version") != version:
            raise DatasetSelectionError("manifest dataset identity does not match request")
        if document.get("status") != "CURATED" or document.get("dataset_type") != expected_type:
            raise DatasetSelectionError(f"dataset must be curated {expected_type}")
        return document

    def _rows(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        artifacts = cast(list[dict[str, Any]], manifest.get("artifacts", []))
        for item in artifacts:
            if item.get("zone") != "curated" or not str(item.get("relative_path", "")).endswith(
                ".parquet"
            ):
                continue
            path = self.root / str(item["relative_path"])
            if not path.is_file() or file_sha256(path) != item.get("sha256"):
                raise DatasetSelectionError(f"curated artifact missing or corrupt: {path}")
            rows.extend(cast(list[dict[str, Any]], pq.ParquetFile(path).read().to_pylist()))
        if not rows:
            raise DatasetSelectionError("curated dataset contains no Parquet rows")
        return rows


def _document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DatasetSelectionError(f"manifest does not exist: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DatasetSelectionError("manifest must be a JSON object")
    return cast(dict[str, Any], value)


def _single(document: dict[str, Any], key: str) -> str:
    values = document.get(key)
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str):
        raise DatasetSelectionError(f"manifest {key} must contain exactly one value")
    return values[0]
