"""Tests for monotonic experiment IDs and immutable evidence bundles."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from ai_trading_lab.analytics.contracts import TradeDirection, TradeRecord
from ai_trading_lab.analytics.metrics import BacktestAnalytics
from ai_trading_lab.backtesting.scenarios import reference_smoke_run
from ai_trading_lab.experiments.contracts import (
    ExperimentSpec,
    ExperimentStatus,
    ResearchVerdict,
)
from ai_trading_lab.experiments.store import (
    ExperimentStore,
    ExperimentValidationError,
    _trade_table,
)

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def _spec(**changes: object) -> ExperimentSpec:
    values = {
        "git_commit": "a" * 40,
        "hypothesis_id": "HYP-INFRASTRUCTURE",
        "strategy_version": "NO-STRATEGY",
        "parameters": (("window", "none"),),
        "verdict": ResearchVerdict.INCONCLUSIVE,
        "decision_reason": "Infrastructure evidence only.",
    }
    values.update(changes)
    return ExperimentSpec(**values)  # type: ignore[arg-type]


def _inputs():  # type: ignore[no-untyped-def]
    request, result = reference_smoke_run()
    return request, result, BacktestAnalytics().analyze(request, result)


def test_record_writes_complete_reproducibility_bundle(tmp_path: Path) -> None:
    request, result, analytics = _inputs()
    store = ExperimentStore(tmp_path, clock=lambda: NOW)
    record = store.record(_spec(), request, result, analytics)

    assert record.experiment_id == "EXP-000001"
    assert record.status is ExperimentStatus.COMPLETE
    assert record.artifact_sha256
    assert record.error is None
    assert record.artifact_path is not None
    manifest = json.loads((record.artifact_path / "manifest.json").read_text())
    metrics = json.loads((record.artifact_path / "metrics.json").read_text())
    trades = pq.read_table(record.artifact_path / "trades.parquet")
    report = (record.artifact_path / "report.md").read_text()

    assert manifest["experiment_id"] == "EXP-000001"
    assert manifest["git_commit"] == "a" * 40
    assert manifest["data"]["dataset_version"] == request.dataset_version
    assert manifest["data"]["symbols"] == ["BTCUSDT"]
    assert manifest["data"]["timeframes"] == ["1m"]
    assert manifest["strategy_version"] == "NO-STRATEGY"
    assert manifest["parameters"] == {"window": "none"}
    assert manifest["backtest"]["execution_assumptions"]["taker_fee_rate"] == "0.00055"
    assert manifest["backtest"]["request_sha256"]
    assert metrics["metrics"]["net_return"]
    assert trades.num_rows == 0
    assert "INCONCLUSIVE" in report
    assert store.get("EXP-000001") == record
    assert store.list_records() == (record,)
    with pytest.raises(KeyError):
        store.get("EXP-999999")


def test_ids_are_monotonic_under_concurrent_writers(tmp_path: Path) -> None:
    request, result, analytics = _inputs()
    store = ExperimentStore(tmp_path, clock=lambda: NOW)

    def record(index: int) -> str:
        spec = _spec(hypothesis_id=f"HYP-{index:02d}")
        return store.record(spec, request, result, analytics).experiment_id

    with ThreadPoolExecutor(max_workers=4) as executor:
        identifiers = tuple(executor.map(record, range(8)))

    assert sorted(identifiers) == [f"EXP-{index:06d}" for index in range(1, 9)]
    assert all(item.status is ExperimentStatus.COMPLETE for item in store.list_records())


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (_spec(git_commit="bad"), "git_commit"),
        (_spec(hypothesis_id=" "), "hypothesis_id"),
        (_spec(strategy_version=" "), "strategy_version"),
        (_spec(decision_reason=" "), "decision_reason"),
        (_spec(parameters=(("x", "1"), ("x", "2"))), "parameter keys"),
        (_spec(parameters=(("", "1"),)), "parameter keys"),
    ],
)
def test_invalid_spec_does_not_consume_an_id(
    tmp_path: Path, spec: ExperimentSpec, message: str
) -> None:
    request, result, analytics = _inputs()
    store = ExperimentStore(tmp_path, clock=lambda: NOW)
    with pytest.raises(ExperimentValidationError, match=message):
        store.record(spec, request, result, analytics)
    assert store.list_records() == ()


def test_inconsistent_evidence_is_rejected(tmp_path: Path) -> None:
    request, result, analytics = _inputs()
    store = ExperimentStore(tmp_path, clock=lambda: NOW)
    with pytest.raises(ExperimentValidationError, match="dataset versions differ"):
        store.record(_spec(), request, replace(result, dataset_version="DS-OTHER"), analytics)
    with pytest.raises(ExperimentValidationError, match="run IDs differ"):
        store.record(_spec(), request, result, replace(analytics, backtest_run_id="BT-OTHER"))
    forged = replace(analytics, metric_version="forged")
    with pytest.raises(ExperimentValidationError, match="not the canonical"):
        store.record(_spec(), request, result, forged)


def test_failed_bundle_is_audited_and_id_is_not_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, result, analytics = _inputs()
    store = ExperimentStore(tmp_path, clock=lambda: NOW)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(ExperimentStore, "_write_bundle", fail)
    with pytest.raises(OSError, match="simulated"):
        store.record(_spec(), request, result, analytics)
    failed = store.get("EXP-000001")
    assert failed.status is ExperimentStatus.FAILED
    assert failed.error == "simulated disk failure"
    assert failed.artifact_path is None


def test_trade_parquet_contract_preserves_exact_optional_values() -> None:
    trade = TradeRecord(
        trade_id="TR-00000001",
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        entry_time=NOW,
        exit_time=NOW,
        quantity=Decimal("1"),
        entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        gross_pnl=Decimal("10"),
        entry_fee=Decimal("0.1"),
        exit_fee=Decimal("0.11"),
        net_pnl=Decimal("9.79"),
        return_on_entry_notional=Decimal("0.0979"),
        initial_risk=Decimal("5"),
        r_multiple=Decimal("1.958"),
        mae=Decimal("-2"),
        mfe=Decimal("12"),
    )
    table = _trade_table((trade,))
    assert table.num_rows == 1
    assert table.column("direction")[0].as_py() == "LONG"
    assert table.column("r_multiple")[0].as_py() == Decimal("1.958000000000000000")
