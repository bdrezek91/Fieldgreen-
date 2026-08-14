"""PHASE 5 benchmark controls; these are not promoted trading strategies."""

from ai_trading_lab.benchmarks.compiler import BenchmarkCompilationError, compile_signals
from ai_trading_lab.benchmarks.contracts import (
    BenchmarkSignal,
    BenchmarkStrategy,
    DistributionSummary,
    FixedQuantityPolicy,
    TargetPosition,
)
from ai_trading_lab.benchmarks.runner import (
    BENCHMARK_POLICY_VERSION,
    DEFAULT_RANDOM_SEEDS,
    BenchmarkRun,
    BenchmarkRunner,
    BenchmarkSuiteResult,
    summarize_distribution,
)
from ai_trading_lab.benchmarks.strategies import (
    BuyAndHold,
    RandomEntry,
    SimpleMeanReversion,
    SimpleTrendFollowing,
)

__all__ = [
    "BENCHMARK_POLICY_VERSION",
    "DEFAULT_RANDOM_SEEDS",
    "BenchmarkCompilationError",
    "BenchmarkRun",
    "BenchmarkRunner",
    "BenchmarkSignal",
    "BenchmarkStrategy",
    "BenchmarkSuiteResult",
    "BuyAndHold",
    "DistributionSummary",
    "FixedQuantityPolicy",
    "RandomEntry",
    "SimpleMeanReversion",
    "SimpleTrendFollowing",
    "TargetPosition",
    "compile_signals",
    "summarize_distribution",
]
