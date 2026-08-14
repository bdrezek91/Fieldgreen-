"""Immutable local/VPS data-lake storage using Parquet and Zstandard."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import UTC
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Final

import pyarrow as pa
import pyarrow.parquet as pq

from ai_trading_lab.data.contracts import Candle, DataZone, Instrument, RawPage
from ai_trading_lab.data.manifest import Artifact, DatasetManifest, file_sha256
from ai_trading_lab.data.validation import ValidationReport

DECIMAL: Final = pa.decimal128(38, 18)
TIMESTAMP: Final = pa.timestamp("ms", tz="UTC")


class DataLake:
    """Filesystem-backed immutable store rooted outside source control."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def write_raw_page(self, page: RawPage) -> Artifact:
        """Persist an exact provider response and request context as canonical gzip JSON."""
        document = {
            "endpoint": page.endpoint,
            "parameters": page.parameters,
            "payload": page.payload,
            "retrieved_at": page.retrieved_at.astimezone(UTC).isoformat(),
        }
        canonical = (json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n").encode()
        digest = hashlib.sha256(canonical).hexdigest()
        endpoint = page.endpoint.strip("/").replace("/", "_")
        relative = Path(DataZone.RAW.value) / "bybit" / endpoint / f"{digest}.json.gz"
        target = self.root / relative
        compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
        self._write_once(target, compressed)
        return Artifact(DataZone.RAW.value, relative.as_posix(), file_sha256(target), None)

    def write_candles(
        self, zone: DataZone, candles: tuple[Candle, ...], *, dataset_version: str
    ) -> tuple[Artifact, ...]:
        """Write candles partitioned by symbol, timeframe, year and month."""
        if zone not in {DataZone.NORMALIZED, DataZone.CURATED, DataZone.QUARANTINE}:
            raise ValueError("candle Parquet is allowed only in normalized, curated or quarantine")
        grouped: dict[tuple[str, str, int, int], list[Candle]] = {}
        for candle in candles:
            key = (
                candle.symbol,
                candle.timeframe.value,
                candle.open_time.year,
                candle.open_time.month,
            )
            grouped.setdefault(key, []).append(candle)

        artifacts: list[Artifact] = []
        for (symbol, timeframe, year, month), rows in sorted(grouped.items()):
            relative = (
                Path(zone.value)
                / "bybit"
                / "linear"
                / "ohlcv"
                / f"timeframe={timeframe}"
                / f"symbol={symbol}"
                / f"year={year:04d}"
                / f"month={month:02d}"
                / f"part-{dataset_version.lower()}.parquet"
            )
            target = self.root / relative
            table = _candle_table(tuple(sorted(rows, key=lambda item: item.open_time)))
            self._write_parquet_once(target, table)
            artifacts.append(
                Artifact(zone.value, relative.as_posix(), file_sha256(target), len(rows))
            )
        return tuple(artifacts)

    def write_instruments(
        self, instruments: tuple[Instrument, ...], *, dataset_version: str
    ) -> Artifact:
        """Write one content-addressed instrument snapshot."""
        relative = (
            Path(DataZone.CURATED.value)
            / "bybit"
            / "linear"
            / "instruments"
            / f"snapshot-{dataset_version.lower()}.parquet"
        )
        target = self.root / relative
        self._write_parquet_once(target, _instrument_table(instruments))
        return Artifact(
            DataZone.CURATED.value, relative.as_posix(), file_sha256(target), len(instruments)
        )

    def write_validation_report(self, dataset_version: str, report: ValidationReport) -> Artifact:
        """Persist all validation findings beside quarantine data."""
        issues = []
        for issue in report.issues:
            item = asdict(issue)
            item["severity"] = issue.severity.value
            item["open_time"] = (
                issue.open_time.astimezone(UTC).isoformat() if issue.open_time else None
            )
            issues.append(item)
        payload = (
            json.dumps({"row_count": report.row_count, "issues": issues}, indent=2, sort_keys=True)
            + "\n"
        ).encode()
        relative = Path(DataZone.QUARANTINE.value) / "reports" / f"{dataset_version.lower()}.json"
        target = self.root / relative
        self._write_once(target, payload)
        return Artifact(
            DataZone.QUARANTINE.value, relative.as_posix(), file_sha256(target), len(issues)
        )

    def write_manifest(self, manifest: DatasetManifest) -> Path:
        """Write a dataset manifest once; the first observed timestamp remains authoritative."""
        target = self.root / "manifests" / f"{manifest.dataset_version.lower()}.json"
        self._write_once(target, manifest.as_json_bytes())
        return target

    @staticmethod
    def _write_once(target: Path, payload: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _write_parquet_once(target: Path, table: pa.Table) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        os.close(descriptor)
        try:
            pq.write_table(
                table,
                temporary,
                compression="zstd",
                use_dictionary=["source"],
                write_statistics=True,
            )
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _candle_table(candles: tuple[Candle, ...]) -> pa.Table:
    schema = pa.schema(
        [
            pa.field("open_time", TIMESTAMP, nullable=False),
            pa.field("open", DECIMAL, nullable=False),
            pa.field("high", DECIMAL, nullable=False),
            pa.field("low", DECIMAL, nullable=False),
            pa.field("close", DECIMAL, nullable=False),
            pa.field("volume", DECIMAL, nullable=False),
            pa.field("turnover", DECIMAL, nullable=False),
            pa.field("source", pa.string(), nullable=False),
        ]
    )
    return pa.Table.from_pylist(
        [
            {
                "open_time": item.open_time.astimezone(UTC),
                "open": _scale(item.open),
                "high": _scale(item.high),
                "low": _scale(item.low),
                "close": _scale(item.close),
                "volume": _scale(item.volume),
                "turnover": _scale(item.turnover),
                "source": item.source,
            }
            for item in candles
        ],
        schema=schema,
    )


def _instrument_table(instruments: tuple[Instrument, ...]) -> pa.Table:
    rows: list[dict[str, object]] = []
    for item in instruments:
        row = asdict(item)
        row["launch_time"] = item.launch_time.astimezone(UTC)
        row["delivery_time"] = item.delivery_time.astimezone(UTC) if item.delivery_time else None
        for key in (
            "tick_size",
            "min_price",
            "max_price",
            "quantity_step",
            "min_order_quantity",
            "max_order_quantity",
            "min_notional",
            "min_leverage",
            "max_leverage",
            "leverage_step",
        ):
            row[key] = _scale(getattr(item, key))
        rows.append(row)
    return pa.Table.from_pylist(rows)


def _scale(value: Decimal) -> Decimal:
    try:
        with localcontext() as context:
            context.prec = 38
            return value.quantize(Decimal("0.000000000000000001"))
    except ArithmeticError as exc:
        raise ValueError(f"decimal value cannot fit decimal128(38,18): {value}") from exc
