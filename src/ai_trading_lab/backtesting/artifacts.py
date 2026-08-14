"""Immutable JSON artifacts for reproducible backtest runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_trading_lab.backtesting.contracts import BacktestRequest, BacktestResult
from ai_trading_lab.serialization import canonical_json_bytes, file_sha256, write_once


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
        payload = canonical_json_bytes(document)
        target = self.root / "backtests" / f"{result.run_id.lower()}.json"
        write_once(target, payload)
        return BacktestArtifact(target, file_sha256(target))
