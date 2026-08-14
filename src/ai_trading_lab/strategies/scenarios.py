"""Offline PHASE 6 proof; synthetic evidence cannot evaluate the hypothesis."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ai_trading_lab.backtesting.contracts import ExecutionAssumptions
from ai_trading_lab.benchmarks.contracts import FixedQuantityPolicy
from ai_trading_lab.benchmarks.runner import BenchmarkRunner
from ai_trading_lab.benchmarks.scenarios import _synthetic_market
from ai_trading_lab.experiments.contracts import ResearchVerdict
from ai_trading_lab.strategies.contracts import RESEARCH_PROTOCOL, EvidenceKind, assess_validation
from ai_trading_lab.strategies.runner import CandidateRunner
from ai_trading_lab.strategies.trend import DualChannelTrend


def strategy_smoke_payload(root: Path, *, git_commit: str = "0" * 40) -> dict[str, object]:
    """Record the candidate and equivalent controls without making an edge claim."""
    candles, instrument = _synthetic_market()
    assumptions = ExecutionAssumptions(max_bar_participation=Decimal("0.05"))
    sizing = FixedQuantityPolicy(Decimal("1"))
    benchmark_suite = BenchmarkRunner(
        dataset_version="DS-PHASE-6-SYNTHETIC-V1",
        candles=candles,
        instrument=instrument,
        initial_cash=Decimal("10000"),
        sizing=sizing,
        assumptions=assumptions,
        artifact_root=root,
        git_commit=git_commit,
    ).run_suite()
    candidate = CandidateRunner(
        dataset_version="DS-PHASE-6-SYNTHETIC-V1",
        candles=candles,
        instrument=instrument,
        initial_cash=Decimal("10000"),
        sizing=sizing,
        assumptions=assumptions,
        artifact_root=root,
        git_commit=git_commit,
    ).run(
        DualChannelTrend(),
        verdict=ResearchVerdict.INCONCLUSIVE,
        decision_reason="Synthetic infrastructure evidence cannot evaluate trading edge.",
    )
    assessment = assess_validation((), EvidenceKind.SYNTHETIC)
    return {
        "status": "PASS",
        "hypothesis_id": RESEARCH_PROTOCOL.hypothesis_id,
        "protocol_version": RESEARCH_PROTOCOL.version,
        "candidate": {
            "name": candidate.name,
            "version": candidate.version,
            "experiment_id": candidate.experiment_id,
            "trades": candidate.analytics.metrics.trades,
            "net_return": str(candidate.analytics.metrics.net_return),
        },
        "random_entry_runs": benchmark_suite.random_net_returns.runs,
        "experiments_recorded": len(benchmark_suite.deterministic)
        + len(benchmark_suite.random)
        + 1,
        "family_decision": assessment.decision.value,
        "test_window": "SEALED",
        "live_trading": "BLOCKED",
    }
