"""Deterministic candidate execution through the owned research stack."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ai_trading_lab.analytics.contracts import AnalyticsResult
from ai_trading_lab.analytics.metrics import BacktestAnalytics
from ai_trading_lab.backtesting.contracts import (
    BacktestRequest,
    BacktestResult,
    ExecutionAssumptions,
    FundingEvent,
    MarkPriceEvent,
)
from ai_trading_lab.backtesting.engine import ReferenceBarBacktestEngine
from ai_trading_lab.benchmarks.contracts import FixedQuantityPolicy
from ai_trading_lab.data.contracts import Candle, Instrument
from ai_trading_lab.experiments.contracts import ExperimentSpec, ResearchVerdict
from ai_trading_lab.experiments.store import ExperimentStore
from ai_trading_lab.signals.compiler import compile_signals
from ai_trading_lab.signals.contracts import SignalStrategy
from ai_trading_lab.strategies.contracts import RESEARCH_PROTOCOL


@dataclass(frozen=True, slots=True)
class CandidateRun:
    """Canonical evidence for one candidate path."""

    name: str
    version: str
    request: BacktestRequest
    result: BacktestResult
    analytics: AnalyticsResult
    experiment_id: str


class CandidateRunner:
    """Run a candidate without giving it execution or verdict authority."""

    def __init__(
        self,
        *,
        dataset_version: str,
        candles: tuple[Candle, ...],
        instrument: Instrument,
        initial_cash: Decimal,
        sizing: FixedQuantityPolicy,
        artifact_root: Path,
        assumptions: ExecutionAssumptions | None = None,
        funding: tuple[FundingEvent, ...] = (),
        marks: tuple[MarkPriceEvent, ...] = (),
        git_commit: str = "0" * 40,
    ) -> None:
        if not candles or any(item.symbol != instrument.symbol for item in candles):
            raise ValueError("candles must be non-empty and match the instrument")
        self.dataset_version = dataset_version
        self.candles = candles
        self.instrument = instrument
        self.initial_cash = initial_cash
        self.sizing = sizing
        self.store = ExperimentStore(artifact_root)
        self.assumptions = assumptions or ExecutionAssumptions()
        self.funding = funding
        self.marks = marks
        self.git_commit = git_commit

    def run(
        self,
        strategy: SignalStrategy,
        *,
        verdict: ResearchVerdict,
        decision_reason: str,
    ) -> CandidateRun:
        """Execute one path and persist its explicit research verdict."""
        orders = compile_signals(
            strategy.generate(self.candles),
            self.candles,
            self.instrument,
            self.sizing,
            max_bar_participation=self.assumptions.max_bar_participation,
        )
        request = BacktestRequest(
            dataset_version=self.dataset_version,
            candles=self.candles,
            instruments=(self.instrument,),
            orders=orders,
            initial_cash=self.initial_cash,
            assumptions=self.assumptions,
            funding=self.funding,
            marks=self.marks,
        )
        result = ReferenceBarBacktestEngine().run(request)
        analytics = BacktestAnalytics().analyze(request, result)
        record = self.store.record(
            ExperimentSpec(
                git_commit=self.git_commit,
                hypothesis_id=RESEARCH_PROTOCOL.hypothesis_id,
                strategy_version=strategy.version,
                parameters=(
                    *strategy.parameters,
                    ("protocol_version", RESEARCH_PROTOCOL.version),
                    ("sizing_policy", self.sizing.version),
                    ("fixed_quantity", str(self.sizing.quantity)),
                ),
                verdict=verdict,
                decision_reason=decision_reason,
            ),
            request,
            result,
            analytics,
        )
        return CandidateRun(
            strategy.name,
            strategy.version,
            request,
            result,
            analytics,
            record.experiment_id,
        )
