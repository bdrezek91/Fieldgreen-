"""Synthetic PHASE 4 registry scenario with no strategy or alpha claim."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ai_trading_lab.analytics.metrics import BacktestAnalytics
from ai_trading_lab.backtesting.scenarios import reference_smoke_run
from ai_trading_lab.experiments.contracts import ExperimentSpec, ResearchVerdict
from ai_trading_lab.experiments.store import ExperimentStore


def experiment_smoke_payload(root: Path) -> dict[str, object]:
    """Persist one synthetic inconclusive experiment and verify its evidence."""
    request, result = reference_smoke_run()
    analytics = BacktestAnalytics().analyze(request, result)
    timestamps = iter(
        (
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC) + timedelta(seconds=1),
        )
    )
    store = ExperimentStore(root, clock=lambda: next(timestamps))
    record = store.record(
        ExperimentSpec(
            git_commit="0" * 40,
            hypothesis_id="PHASE-4-INFRASTRUCTURE-SMOKE",
            strategy_version="NO-STRATEGY",
            parameters=(),
            verdict=ResearchVerdict.INCONCLUSIVE,
            decision_reason="Synthetic infrastructure scenario; no trading hypothesis evaluated.",
        ),
        request,
        result,
        analytics,
    )
    artifact = record.artifact_path
    if artifact is None:
        raise RuntimeError("completed smoke experiment has no artifact path")
    required = ("manifest.json", "metrics.json", "trades.parquet", "report.md")
    if not all((artifact / name).is_file() for name in required):
        raise RuntimeError("experiment evidence is incomplete")
    return {
        "status": record.status.value,
        "experiment_id": record.experiment_id,
        "verdict": record.verdict.value,
        "backtest_run_id": record.backtest_run_id,
        "trade_count": analytics.metrics.trades,
        "unavailable_metrics": analytics.metrics.unavailable_metrics,
        "artifact_sha256": record.artifact_sha256,
        "live_trading": "BLOCKED",
    }
