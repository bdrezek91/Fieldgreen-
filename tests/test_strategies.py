from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_trading_lab.backtesting.contracts import ExecutionAssumptions
from ai_trading_lab.benchmarks.contracts import FixedQuantityPolicy
from ai_trading_lab.benchmarks.scenarios import _synthetic_market
from ai_trading_lab.data.contracts import Timeframe
from ai_trading_lab.experiments.contracts import ResearchVerdict
from ai_trading_lab.signals.contracts import PositionSignal, TargetPosition
from ai_trading_lab.strategies.contracts import (
    EXPECTED_VALIDATION_CELLS,
    RESEARCH_PROTOCOL,
    EvidenceKind,
    FamilyDecision,
    ValidationCell,
    assess_validation,
)
from ai_trading_lab.strategies.runner import CandidateRunner
from ai_trading_lab.strategies.scenarios import strategy_smoke_payload
from ai_trading_lab.strategies.trend import DualChannelTrend
from ai_trading_lab.strategies.validation_matrix import ValidationMatrixRunner


def test_protocol_is_frozen_before_real_results() -> None:
    assert RESEARCH_PROTOCOL.hypothesis_id == "HYP-TREND-DUAL-CHANNEL-001"
    assert RESEARCH_PROTOCOL.primary_metric == "median_net_return_across_validation_matrix"
    assert RESEARCH_PROTOCOL.minimum_total_trades == 60
    assert RESEARCH_PROTOCOL.required_cell_passes == 4
    assert RESEARCH_PROTOCOL.funding_required
    assert len(EXPECTED_VALIDATION_CELLS) == 6
    assert [item.name for item in RESEARCH_PROTOCOL.windows] == ["TRAIN", "VALIDATION", "TEST"]
    assert RESEARCH_PROTOCOL.windows[-1].sealed


def test_dual_channel_parameters_and_input_validation() -> None:
    strategy = DualChannelTrend()
    assert strategy.parameters == (("entry_lookback", "55"), ("exit_lookback", "20"))
    with pytest.raises(ValueError, match="entry lookback"):
        DualChannelTrend(20, 20)
    with pytest.raises(ValueError, match="entry lookback"):
        DualChannelTrend(3, 1)
    candles, _instrument = _synthetic_market()
    with pytest.raises(ValueError, match="three candles"):
        strategy.generate(candles[:2])
    with pytest.raises(ValueError, match="one symbol"):
        strategy.generate((candles[0], replace(candles[1], symbol="ETHUSDT"), candles[2]))
    with pytest.raises(ValueError, match="one timeframe"):
        strategy.generate(
            (candles[0], replace(candles[1], timeframe=Timeframe.ONE_DAY), candles[2])
        )


def test_dual_channel_is_prefix_only_and_symmetric() -> None:
    candles, _instrument = _synthetic_market()
    strategy = DualChannelTrend()
    full = strategy.generate(candles)
    prefix = candles[:180]
    partial = strategy.generate(prefix)
    cutoff = prefix[-2].close_time
    assert tuple(item for item in full if item.generated_at < cutoff) == tuple(
        item for item in partial if item.generated_at < cutoff
    )
    assert {item.target for item in full} == {
        TargetPosition.LONG,
        TargetPosition.SHORT,
        TargetPosition.FLAT,
    }
    assert full[-1].reason == "forced-test-window-exit"


def test_position_signal_rejects_naive_or_empty_fields() -> None:
    with pytest.raises(ValueError, match="required"):
        PositionSignal("", datetime(2026, 1, 1), TargetPosition.FLAT, "")
    with pytest.raises(ValueError, match="timezone-aware"):
        PositionSignal("BTCUSDT", datetime(2026, 1, 1), TargetPosition.FLAT, "reason")


def test_family_gate_never_uses_synthetic_evidence() -> None:
    result = assess_validation((), EvidenceKind.SYNTHETIC)
    assert result.decision is FamilyDecision.INCONCLUSIVE
    assert result.median_candidate_return is None


def test_family_gate_requires_complete_matrix_and_activity() -> None:
    cells = _cells(candidate=Decimal("0.10"), trades=10)
    incomplete = assess_validation(cells[:-1], EvidenceKind.CURATED_BYBIT)
    assert incomplete.decision is FamilyDecision.INCONCLUSIVE
    low_activity = assess_validation(
        tuple(replace(item, candidate_trades=5) for item in cells),
        EvidenceKind.CURATED_BYBIT,
    )
    assert low_activity.decision is FamilyDecision.INCONCLUSIVE
    with pytest.raises(ValueError, match="negative"):
        assess_validation(
            (replace(cells[0], candidate_trades=-1), *cells[1:]),
            EvidenceKind.CURATED_BYBIT,
        )
    no_funding = assess_validation(
        (replace(cells[0], funding_included=False), *cells[1:]),
        EvidenceKind.CURATED_BYBIT,
    )
    assert no_funding.decision is FamilyDecision.INCONCLUSIVE
    mixed_assumptions = assess_validation(
        (replace(cells[0], assumptions_version="other"), *cells[1:]),
        EvidenceKind.CURATED_BYBIT,
    )
    assert mixed_assumptions.decision is FamilyDecision.INCONCLUSIVE


def test_family_gate_advances_or_rejects_deterministically() -> None:
    passed = assess_validation(
        _cells(candidate=Decimal("0.10"), trades=10), EvidenceKind.CURATED_BYBIT
    )
    assert passed.decision is FamilyDecision.ADVANCE_TO_PHASE_7
    assert passed.total_trades == 60
    assert passed.positive_cells == 6
    assert passed.trend_beats == 6
    assert passed.random_p95_beats == 6
    rejected = assess_validation(
        _cells(candidate=Decimal("0.01"), trades=10), EvidenceKind.CURATED_BYBIT
    )
    assert rejected.decision is FamilyDecision.REJECTED


def test_candidate_runner_records_explicit_inconclusive_evidence(tmp_path: Path) -> None:
    candles, instrument = _synthetic_market()
    run = CandidateRunner(
        dataset_version="DS-TEST",
        candles=candles,
        instrument=instrument,
        initial_cash=Decimal("10000"),
        sizing=FixedQuantityPolicy(Decimal("1")),
        artifact_root=tmp_path,
        assumptions=ExecutionAssumptions(max_bar_participation=Decimal("0.05")),
    ).run(
        DualChannelTrend(),
        verdict=ResearchVerdict.INCONCLUSIVE,
        decision_reason="Synthetic test only.",
    )
    assert run.experiment_id == "EXP-000001"
    assert run.name == "DUAL_CHANNEL_TREND"
    assert run.result.fills
    assert (tmp_path / "experiments" / run.experiment_id / "manifest.json").is_file()
    with pytest.raises(ValueError, match="non-empty"):
        CandidateRunner(
            dataset_version="DS-TEST",
            candles=(),
            instrument=instrument,
            initial_cash=Decimal("10000"),
            sizing=FixedQuantityPolicy(Decimal("1")),
            artifact_root=tmp_path / "invalid",
        )


def test_strategy_smoke_records_candidate_after_controls(tmp_path: Path) -> None:
    payload = strategy_smoke_payload(tmp_path)
    assert payload["status"] == "PASS"
    assert payload["experiments_recorded"] == 104
    assert payload["random_entry_runs"] == 100
    assert payload["family_decision"] == "INCONCLUSIVE"
    assert payload["test_window"] == "SEALED"
    assert payload["live_trading"] == "BLOCKED"


def test_real_matrix_runner_uses_only_frozen_validation_cells(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candles, base_instrument = _synthetic_market()

    class Loader:
        def __init__(self, _root: Path) -> None:
            pass

        def instruments(self, _version: str) -> tuple[object, ...]:
            return tuple(
                replace(base_instrument, symbol=symbol) for symbol in RESEARCH_PROTOCOL.symbols
            )

        def resolve_unique(self, **kwargs: str) -> str:
            assert kwargs["start"].startswith("2024-01-01")
            assert kwargs["end"].startswith("2025-01-01")
            return f"DS-{kwargs['dataset_type']}-{kwargs['symbol']}-{kwargs['timeframe']}"

        def funding(self, version: str) -> tuple[object, ...]:
            symbol = next(symbol for symbol in RESEARCH_PROTOCOL.symbols if symbol in version)
            return (
                SimpleNamespace(symbol=symbol, timestamp=candles[0].open_time, rate=Decimal(0)),
            )

        def mark_prices(self, _version: str) -> tuple[object, ...]:
            return (SimpleNamespace(open_time=candles[0].open_time, open=Decimal("100")),)

        def candles(self, version: str) -> tuple[object, ...]:
            symbol = next(symbol for symbol in RESEARCH_PROTOCOL.symbols if symbol in version)
            timeframe = Timeframe.FOUR_HOURS if version.endswith("4h") else Timeframe.ONE_HOUR
            return tuple(replace(item, symbol=symbol, timeframe=timeframe) for item in candles[:3])

    metrics = SimpleNamespace(net_return=Decimal("0.10"), max_drawdown=Decimal("0.10"), trades=10)
    trend_metrics = SimpleNamespace(net_return=Decimal("0.03"), max_drawdown=Decimal("0.10"))

    class Benchmarks:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run_suite(self) -> object:
            trend = SimpleNamespace(
                name="SIMPLE_TREND_FOLLOWING",
                analytics=SimpleNamespace(metrics=trend_metrics),
            )
            return SimpleNamespace(
                deterministic=(trend, object(), object()),
                random=tuple(object() for _ in range(100)),
                random_net_returns=SimpleNamespace(p95=Decimal("0.05")),
            )

    class Candidate:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(self, *_args: object, **_kwargs: object) -> object:
            return SimpleNamespace(analytics=SimpleNamespace(metrics=metrics))

    monkeypatch.setattr("ai_trading_lab.strategies.validation_matrix.CuratedDataLoader", Loader)
    monkeypatch.setattr("ai_trading_lab.strategies.validation_matrix.BenchmarkRunner", Benchmarks)
    monkeypatch.setattr("ai_trading_lab.strategies.validation_matrix.CandidateRunner", Candidate)
    result = ValidationMatrixRunner(
        data_root=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
        instrument_dataset_version="DS-INSTRUMENTS",
        git_commit="0" * 40,
    ).run()
    assert result.assessment.decision is FamilyDecision.ADVANCE_TO_PHASE_7
    assert len(result.cells) == 6
    assert result.experiments_recorded == 624
    assert '"test_window": "SEALED"' in result.artifact_path.read_text()


def _cells(*, candidate: Decimal, trades: int) -> tuple[ValidationCell, ...]:
    return tuple(
        ValidationCell(
            symbol=symbol,
            timeframe=timeframe,
            window_name="VALIDATION",
            dataset_version=f"DS-{symbol}-{timeframe.value}",
            assumptions_version="execution-assumptions-v1",
            funding_included=True,
            candidate_net_return=candidate,
            trend_net_return=Decimal("0.03"),
            random_p95_net_return=Decimal("0.05"),
            candidate_max_drawdown=Decimal("0.10"),
            trend_max_drawdown=Decimal("0.10"),
            candidate_trades=trades,
        )
        for symbol, timeframe in sorted(
            EXPECTED_VALIDATION_CELLS, key=lambda item: (item[0], item[1].value)
        )
    )
