"""Immutable JSON artifacts for reproducible backtest runs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from ai_trading_lab.backtesting.contracts import BacktestRequest, BacktestResult


@dataclass(frozen=True, slots=True)
class BacktestArtifact:
    """Location and hash of one immutable result document."""

    path: Path
    sha256: str


class BacktestArtifactStore:
    """Persist canonical ledgers and request summaries outside Git."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def write(self, request: BacktestRequest, result: BacktestResult) -> BacktestArtifact:
        """Write a result once using its deterministic run ID."""
        if result.dataset_version != request.dataset_version:
            raise ValueError("result and request dataset versions differ")
        document = {
            "schema_version": "backtest-artifact-v1",
            "request": {
                "dataset_version": request.dataset_version,
                "candle_count": len(request.candles),
                "start": min(item.open_time for item in request.candles),
                "end": max(item.close_time for item in request.candles),
                "instruments": request.instruments,
                "orders": request.orders,
                "initial_cash": request.initial_cash,
                "assumptions": request.assumptions,
                "funding_count": len(request.funding),
                "mark_count": len(request.marks),
            },
            "result": result,
        }
        payload = (json.dumps(_jsonable(document), indent=2, sort_keys=True) + "\n").encode()
        target = self.root / "backtests" / f"{result.run_id.lower()}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != payload:
                raise FileExistsError(f"immutable artifact differs: {target}")
        else:
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
        return BacktestArtifact(target, _sha256(target))


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
