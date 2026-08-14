"""Deterministic execution and evidence recording for PHASE 5 controls."""

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
from ai_trading_lab.benchmarks.compiler import compile_signals
from ai_trading_lab.benchmarks.contracts import (
    BenchmarkStrategy,
    DistributionSummary,
    FixedQuantityPolicy,
)
from ai_trading_lab.benchmarks.strategies import (
    BuyAndHold,
    RandomEntry,
    SimpleMeanReversion,
    SimpleTrendFollowing,
)
from ai_trading_lab.data.contracts import Candle, Instrument
from ai_trading_lab.experiments.contracts import ExperimentSpec, ResearchVerdict
from ai_trading_lab.experiments.store import ExperimentStore

BENCHMARK_POLICY_VERSION = "benchmark-comparison-policy-v1"
DEFAULT_RANDOM_SEEDS = 100


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    """Canonical evidence for one benchmark path."""

    name: str
    version: str
    parameters: tuple[tuple[str, str], ...]
    request: BacktestRequest
    result: BacktestResult
    analytics: AnalyticsResult
    experiment_id: str | None


@dataclass(frozen=True, slots=True)
class BenchmarkSuiteResult:
    """Four control families, with Random Entry represented by a distribution."""

    deterministic: tuple[BenchmarkRun, ...]
    random: tuple[BenchmarkRun, ...]
    random_net_returns: DistributionSummary
    policy_version: str = BENCHMARK_POLICY_VERSION


class BenchmarkRunner:
    """Run all controls through one compiler, engine, analytics and optional registry."""

    def __init__(
        self,
        *,
        dataset_version: str,
        candles: tuple[Candle, ...],
        instrument: Instrument,
        initial_cash: Decimal,
        sizing: FixedQuantityPolicy,
        assumptions: ExecutionAssumptions | None = None,
        funding: tuple[FundingEvent, ...] = (),
        marks: tuple[MarkPriceEvent, ...] = (),
        artifact_root: Path | None = None,
        git_commit: str = "0" * 40,
    ) -> None:
        if not candles or any(item.symbol != instrument.symbol for item in candles):
            raise ValueError("candles must be non-empty and match the instrument")
        self.dataset_version = dataset_version
        self.candles = candles
        self.instrument = instrument
        self.initial_cash = initial_cash
        self.sizing = sizing
        self.assumptions = assumptions or ExecutionAssumptions()
        self.funding = funding
        self.marks = marks
        self.store = ExperimentStore(artifact_root) if artifact_root is not None else None
        self.git_commit = git_commit

    def run(self, strategy: BenchmarkStrategy) -> BenchmarkRun:
        """Execute and optionally persist one benchmark as INCONCLUSIVE evidence."""
        signals = strategy.generate(self.candles)
        orders = compile_signals(
            signals,
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
        experiment_id: str | None = None
        if self.store is not None:
            parameters = (
                *strategy.parameters,
                ("benchmark_policy", BENCHMARK_POLICY_VERSION),
                ("sizing_policy", self.sizing.version),
                ("fixed_quantity", str(self.sizing.quantity)),
            )
            record = self.store.record(
                ExperimentSpec(
                    git_commit=self.git_commit,
                    hypothesis_id=f"PHASE-5-{strategy.name}",
                    strategy_version=strategy.version,
                    parameters=parameters,
                    verdict=ResearchVerdict.INCONCLUSIVE,
                    decision_reason=(
                        "Control evidence only; PHASE 5 does not establish or promote trading edge."
                    ),
                ),
                request,
                result,
                analytics,
            )
            experiment_id = record.experiment_id
        return BenchmarkRun(
            strategy.name,
            strategy.version,
            strategy.parameters,
            request,
            result,
            analytics,
            experiment_id,
        )

    def run_suite(self, *, random_seeds: int = DEFAULT_RANDOM_SEEDS) -> BenchmarkSuiteResult:
        """Run frozen deterministic controls plus seeds [0, random_seeds)."""
        if random_seeds < 20:
            raise ValueError("the initial Random Entry distribution requires at least 20 seeds")
        deterministic = tuple(
            self.run(strategy)
            for strategy in (BuyAndHold(), SimpleTrendFollowing(), SimpleMeanReversion())
        )
        random = tuple(self.run(RandomEntry(seed)) for seed in range(random_seeds))
        returns = tuple(item.analytics.metrics.net_return for item in random)
        return BenchmarkSuiteResult(deterministic, random, summarize_distribution(returns))


def summarize_distribution(values: tuple[Decimal, ...]) -> DistributionSummary:
    """Summarize values with deterministic nearest-rank percentiles."""
    if not values:
        raise ValueError("distribution values are required")
    ordered = sorted(values)

    def percentile(probability: Decimal) -> Decimal:
        index = int((Decimal(len(ordered) - 1) * probability).to_integral_value())
        return ordered[index]

    return DistributionSummary(
        runs=len(ordered),
        minimum=ordered[0],
        p05=percentile(Decimal("0.05")),
        median=percentile(Decimal("0.50")),
        mean=sum(ordered, Decimal(0)) / Decimal(len(ordered)),
        p95=percentile(Decimal("0.95")),
        maximum=ordered[-1],
    )
