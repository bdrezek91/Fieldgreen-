"""One-shot execution of the frozen PHASE 6 real-data validation matrix."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time
from pathlib import Path

from ai_trading_lab.backtesting.contracts import ExecutionAssumptions, FundingEvent, MarkPriceEvent
from ai_trading_lab.benchmarks.contracts import FixedQuantityPolicy
from ai_trading_lab.benchmarks.runner import BenchmarkRunner
from ai_trading_lab.data.contracts import Timeframe
from ai_trading_lab.data.loader import CuratedDataLoader
from ai_trading_lab.experiments.contracts import ResearchVerdict
from ai_trading_lab.serialization import canonical_json_bytes, write_once
from ai_trading_lab.strategies.contracts import (
    RESEARCH_PROTOCOL,
    VALIDATION_FIXED_QUANTITIES,
    VALIDATION_INITIAL_CASH,
    EvidenceKind,
    FamilyAssessment,
    ValidationCell,
    assess_validation,
)
from ai_trading_lab.strategies.runner import CandidateRunner
from ai_trading_lab.strategies.trend import DualChannelTrend


@dataclass(frozen=True, slots=True)
class ValidationMatrixResult:
    """Frozen gate output and its six comparable cells."""

    assessment: FamilyAssessment
    cells: tuple[ValidationCell, ...]
    experiments_recorded: int
    artifact_path: Path


class ValidationMatrixRunner:
    """Resolve only VALIDATION manifests; this class has no TEST lookup path."""

    def __init__(
        self,
        *,
        data_root: Path,
        artifact_root: Path,
        instrument_dataset_version: str,
        git_commit: str,
    ) -> None:
        self.loader = CuratedDataLoader(data_root)
        self.artifact_root = artifact_root
        self.instrument_dataset_version = instrument_dataset_version
        self.git_commit = git_commit

    def run(self) -> ValidationMatrixResult:
        """Run exactly six cells and persist the immutable family decision."""
        window = next(item for item in RESEARCH_PROTOCOL.windows if item.name == "VALIDATION")
        start = datetime.combine(window.start, time.min, tzinfo=UTC)
        end = datetime.combine(window.end, time.min, tzinfo=UTC)
        start_iso, end_iso = start.isoformat(), end.isoformat()
        instruments = {
            item.symbol: item for item in self.loader.instruments(self.instrument_dataset_version)
        }
        quantities = dict(VALIDATION_FIXED_QUANTITIES)
        assumptions = ExecutionAssumptions(version="phase-6-validation-execution-v1")
        cells: list[ValidationCell] = []
        experiments = 0
        for symbol in RESEARCH_PROTOCOL.symbols:
            instrument = instruments[symbol]
            funding_version = self.loader.resolve_unique(
                dataset_type="funding_v1",
                symbol=symbol,
                timeframe=f"{instrument.funding_interval_minutes}m",
                start=start_iso,
                end=end_iso,
            )
            mark_version = self.loader.resolve_unique(
                dataset_type="mark_price_ohlc_v1",
                symbol=symbol,
                timeframe=Timeframe.ONE_HOUR.value,
                start=start_iso,
                end=end_iso,
            )
            funding_rates = self.loader.funding(funding_version)
            mark_rows = self.loader.mark_prices(mark_version)
            mark_by_time = {item.open_time: item.open for item in mark_rows}
            funding = tuple(
                FundingEvent(item.symbol, item.timestamp, item.rate, mark_by_time[item.timestamp])
                for item in funding_rates
            )
            for timeframe in RESEARCH_PROTOCOL.timeframes:
                candle_version = self.loader.resolve_unique(
                    dataset_type="ohlcv_v1",
                    symbol=symbol,
                    timeframe=timeframe.value,
                    start=start_iso,
                    end=end_iso,
                )
                candles = self.loader.candles(candle_version)
                candle_times = {item.open_time for item in candles}
                marks = tuple(
                    MarkPriceEvent(symbol, timestamp, price)
                    for timestamp, price in sorted(mark_by_time.items())
                    if timestamp in candle_times
                )
                dataset_version = _composite_version(
                    candle_version, funding_version, mark_version, self.instrument_dataset_version
                )
                sizing = FixedQuantityPolicy(quantities[symbol], "phase-6-fixed-quantity-v1")
                suite = BenchmarkRunner(
                    dataset_version=dataset_version,
                    candles=candles,
                    instrument=instrument,
                    initial_cash=VALIDATION_INITIAL_CASH,
                    sizing=sizing,
                    assumptions=assumptions,
                    funding=funding,
                    marks=marks,
                    artifact_root=self.artifact_root,
                    git_commit=self.git_commit,
                ).run_suite()
                candidate = CandidateRunner(
                    dataset_version=dataset_version,
                    candles=candles,
                    instrument=instrument,
                    initial_cash=VALIDATION_INITIAL_CASH,
                    sizing=sizing,
                    assumptions=assumptions,
                    funding=funding,
                    marks=marks,
                    artifact_root=self.artifact_root,
                    git_commit=self.git_commit,
                ).run(
                    DualChannelTrend(),
                    verdict=ResearchVerdict.INCONCLUSIVE,
                    decision_reason="Pending the frozen six-cell PHASE 6 family gate.",
                )
                trend = next(
                    item for item in suite.deterministic if item.name == "SIMPLE_TREND_FOLLOWING"
                )
                cells.append(
                    ValidationCell(
                        symbol=symbol,
                        timeframe=timeframe,
                        window_name="VALIDATION",
                        dataset_version=dataset_version,
                        assumptions_version=assumptions.version,
                        funding_included=True,
                        candidate_net_return=candidate.analytics.metrics.net_return,
                        trend_net_return=trend.analytics.metrics.net_return,
                        random_p95_net_return=suite.random_net_returns.p95,
                        candidate_max_drawdown=candidate.analytics.metrics.max_drawdown,
                        trend_max_drawdown=trend.analytics.metrics.max_drawdown,
                        candidate_trades=candidate.analytics.metrics.trades,
                    )
                )
                experiments += len(suite.deterministic) + len(suite.random) + 1
        cell_tuple = tuple(cells)
        assessment = assess_validation(cell_tuple, EvidenceKind.CURATED_BYBIT)
        target = self.artifact_root / "strategy-family-gates" / "phase-6-validation-v1.json"
        write_once(
            target,
            canonical_json_bytes(
                {
                    "protocol": RESEARCH_PROTOCOL.version,
                    "hypothesis_id": RESEARCH_PROTOCOL.hypothesis_id,
                    "assessment": asdict(assessment),
                    "cells": [asdict(item) for item in cell_tuple],
                    "experiments_recorded": experiments,
                    "test_window": "SEALED",
                    "live_trading": "BLOCKED",
                }
            ),
        )
        return ValidationMatrixResult(assessment, cell_tuple, experiments, target)


def _composite_version(*versions: str) -> str:
    digest = hashlib.sha256("|".join(versions).encode()).hexdigest()
    return f"DS-{digest[:20].upper()}"
