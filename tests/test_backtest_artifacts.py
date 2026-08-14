"""Persistence tests for immutable backtest artifacts."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_lab.backtesting.artifacts import BacktestArtifactStore
from ai_trading_lab.backtesting.contracts import BacktestRequest, OrderIntent, OrderType, Side
from ai_trading_lab.backtesting.engine import ReferenceBarBacktestEngine


def test_artifact_is_canonical_idempotent_and_keeps_decimal_strings(
    tmp_path, candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    candles = (candle_factory(0), candle_factory(1))
    request = BacktestRequest(
        dataset_version="DS-ARTIFACT",
        candles=candles,
        instruments=(instrument_factory(),),
        orders=(
            OrderIntent(
                "ENTRY",
                "BTCUSDT",
                Side.BUY,
                OrderType.MARKET,
                Decimal("1"),
                datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            ),
        ),
        initial_cash=Decimal("10000.00"),
    )
    result = ReferenceBarBacktestEngine().run(request)
    store = BacktestArtifactStore(tmp_path)

    first = store.write(request, result)
    second = store.write(request, result)
    document = json.loads(first.path.read_text())

    assert first == second
    assert document["schema_version"] == "backtest-artifact-v1"
    assert document["request"]["initial_cash"] == "10000.00"
    assert document["result"]["run_id"] == result.run_id


def test_artifact_rejects_dataset_identity_mismatch(
    tmp_path, candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    request = BacktestRequest(
        dataset_version="DS-A",
        candles=(candle_factory(0),),
        instruments=(instrument_factory(),),
        orders=(),
        initial_cash=Decimal("100"),
    )
    result = ReferenceBarBacktestEngine().run(request)
    mismatched = BacktestRequest(
        dataset_version="DS-B",
        candles=request.candles,
        instruments=request.instruments,
        orders=(),
        initial_cash=request.initial_cash,
    )
    with pytest.raises(ValueError, match="dataset versions differ"):
        BacktestArtifactStore(tmp_path).write(mismatched, result)


def test_existing_artifact_cannot_be_overwritten(
    tmp_path, candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    request = BacktestRequest(
        dataset_version="DS-IMMUTABLE",
        candles=(candle_factory(0),),
        instruments=(instrument_factory(),),
        orders=(),
        initial_cash=Decimal("100"),
    )
    result = ReferenceBarBacktestEngine().run(request)
    store = BacktestArtifactStore(tmp_path)
    store.write(request, result)
    with pytest.raises(FileExistsError, match="immutable artifact differs"):
        store.write(request, replace(result, final_cash=Decimal("99")))
