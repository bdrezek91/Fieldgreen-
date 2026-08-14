"""Content-addressed dataset identity and lineage manifests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ai_trading_lab.data.contracts import Candle


@dataclass(frozen=True, slots=True)
class Artifact:
    """One immutable file belonging to a dataset version."""

    zone: str
    relative_path: str
    sha256: str
    rows: int | None


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Auditable metadata required to reproduce a dataset transformation."""

    dataset_version: str
    dataset_type: str
    provider: str
    category: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    start: str | None
    end: str | None
    generated_at: str
    status: str
    transformation: str
    parent_versions: tuple[str, ...]
    artifacts: tuple[Artifact, ...]
    row_count: int
    validation_errors: int
    validation_warnings: int

    def as_json_bytes(self) -> bytes:
        """Serialize deterministically for stable storage and review."""
        return (json.dumps(asdict(self), indent=2, sort_keys=True) + "\n").encode()


def candle_dataset_version(
    candles: tuple[Candle, ...], *, transformation: str, identity: str = ""
) -> str:
    """Build a content-derived version from canonical candle values and transformation."""
    digest = hashlib.sha256()
    digest.update(f"ohlcv-v1\n{transformation}\n{identity}\n".encode())
    for candle in sorted(
        candles, key=lambda item: (item.symbol, item.timeframe.value, item.open_time)
    ):
        fields = (
            candle.symbol,
            candle.timeframe.value,
            candle.open_time.astimezone(UTC).isoformat(),
            _decimal(candle.open),
            _decimal(candle.high),
            _decimal(candle.low),
            _decimal(candle.close),
            _decimal(candle.volume),
            _decimal(candle.turnover),
            candle.source,
        )
        digest.update(("|".join(fields) + "\n").encode())
    return f"DS-{digest.hexdigest()[:20].upper()}"


def file_sha256(path: Path) -> str:
    """Hash a file without loading it entirely into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def utc_iso(value: datetime | None) -> str | None:
    """Serialize an optional aware timestamp in UTC."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("manifest timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
