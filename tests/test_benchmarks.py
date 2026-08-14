from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trading_lab.backtesting.contracts import ExecutionAssumptions
from ai_trading_lab.benchmarks.compiler import BenchmarkCompilationError, compile_signals
from ai_trading_lab.benchmarks.contracts import (
    BenchmarkSignal,
    FixedQuantityPolicy,
    TargetPosition,
)
from ai_trading_lab.benchmarks.runner import BenchmarkRunner, summarize_distribution
from ai_trading_lab.benchmarks.scenarios import _synthetic_market, benchmark_smoke_payload
from ai_trading_lab.benchmarks.strategies import (
    BuyAndHold,
    RandomEntry,
    SimpleMeanReversion,
    SimpleTrendFollowing,
)


def test_buy_and_hold_uses_next_bar_and_forced_flat() -> None:
    candles, instrument = _synthetic_market()
    signals = BuyAndHold().generate(candles)
    orders = compile_signals(
        signals,
        candles,
        instrument,
        FixedQuantityPolicy(Decimal("1")),
        max_bar_participation=Decimal("0.05"),
    )
    assert [item.target for item in signals] == [TargetPosition.LONG, TargetPosition.FLAT]
    assert orders[0].submitted_at == candles[0].close_time
    assert orders[1].reduce_only


def test_random_entry_is_reproducible_and_seeded() -> None:
    candles, _instrument = _synthetic_market()
    first = RandomEntry(7).generate(candles)
    assert first == RandomEntry(7).generate(tuple(reversed(candles)))
    assert first != RandomEntry(8).generate(candles)
    assert first[-1].target is TargetPosition.FLAT
    assert RandomEntry(7).parameters[-1] == ("seed", "7")


@pytest.mark.parametrize("strategy", [SimpleTrendFollowing(), SimpleMeanReversion()])
def test_deterministic_benchmarks_are_prefix_only(strategy: object) -> None:
    candles, _instrument = _synthetic_market()
    full = strategy.generate(candles)  # type: ignore[attr-defined]
    prefix = candles[:150]
    partial = strategy.generate(prefix)  # type: ignore[attr-defined]
    cutoff = prefix[-2].close_time
    assert tuple(item for item in full if item.generated_at < cutoff) == tuple(
        item for item in partial if item.generated_at < cutoff
    )


def test_fixed_parameters_and_validation() -> None:
    assert SimpleTrendFollowing().parameters == (("lookback", "50"),)
    assert SimpleMeanReversion().parameters == (("entry_z", "2"), ("lookback", "20"))
    with pytest.raises(ValueError):
        FixedQuantityPolicy(Decimal(0))
    with pytest.raises(ValueError):
        FixedQuantityPolicy(Decimal(1), "")
    with pytest.raises(ValueError):
        BenchmarkSignal("", datetime(2026, 1, 1), TargetPosition.FLAT, "test")
    with pytest.raises(ValueError, match="timezone-aware"):
        BenchmarkSignal("BTCUSDT", datetime(2026, 1, 1), TargetPosition.FLAT, "test")
    with pytest.raises(ValueError):
        RandomEntry(1, Decimal(0))
    with pytest.raises(ValueError):
        RandomEntry(1, holding_bars=0)
    with pytest.raises(ValueError):
        SimpleTrendFollowing(1)
    with pytest.raises(ValueError):
        SimpleMeanReversion(1)


def test_strategy_input_validation() -> None:
    candles, _instrument = _synthetic_market()
    with pytest.raises(ValueError, match="three candles"):
        BuyAndHold().generate(candles[:2])
    other_symbol = replace(candles[1], symbol="ETHUSDT")
    with pytest.raises(ValueError, match="one symbol"):
        BuyAndHold().generate((candles[0], other_symbol, candles[2]))
    other_timeframe = replace(candles[1], timeframe=candles[1].timeframe.ONE_DAY)
    with pytest.raises(ValueError, match="one timeframe"):
        BuyAndHold().generate((candles[0], other_timeframe, candles[2]))


def test_compiler_rejects_ambiguous_or_unfair_inputs() -> None:
    candles, instrument = _synthetic_market()
    sizing = FixedQuantityPolicy(Decimal("1"))
    valid = BenchmarkSignal("BTCUSDT", candles[0].close_time, TargetPosition.LONG, "test")
    flat = BenchmarkSignal("BTCUSDT", candles[1].close_time, TargetPosition.FLAT, "test")
    with pytest.raises(BenchmarkCompilationError, match="finish"):
        compile_signals((valid,), candles, instrument, sizing, max_bar_participation=Decimal("1"))
    with pytest.raises(BenchmarkCompilationError, match="one target"):
        compile_signals(
            (valid, replace(valid, target=TargetPosition.SHORT)),
            candles,
            instrument,
            sizing,
            max_bar_participation=Decimal("1"),
        )
    with pytest.raises(BenchmarkCompilationError, match="redundant"):
        compile_signals(
            (valid, replace(flat, target=TargetPosition.LONG)),
            candles,
            instrument,
            sizing,
            max_bar_participation=Decimal("1"),
        )
    with pytest.raises(BenchmarkCompilationError, match="known"):
        compile_signals(
            (replace(valid, symbol="ETHUSDT"), flat),
            candles,
            instrument,
            sizing,
            max_bar_participation=Decimal("1"),
        )
    with pytest.raises(BenchmarkCompilationError, match="volume"):
        compile_signals(
            (valid, flat),
            candles,
            instrument,
            FixedQuantityPolicy(Decimal("100")),
            max_bar_participation=Decimal("0.01"),
        )
    with pytest.raises(BenchmarkCompilationError, match="quantity_step"):
        compile_signals(
            (valid, flat),
            candles,
            instrument,
            FixedQuantityPolicy(Decimal("1.0001")),
            max_bar_participation=Decimal("1"),
        )
    with pytest.raises(BenchmarkCompilationError, match="order limits"):
        compile_signals(
            (valid, flat),
            candles,
            instrument,
            FixedQuantityPolicy(Decimal("1001")),
            max_bar_participation=Decimal("1"),
        )
    tiny_maximum = replace(instrument, max_order_quantity=Decimal("1"))
    flip = replace(flat, target=TargetPosition.SHORT)
    final_flat = BenchmarkSignal("BTCUSDT", candles[2].close_time, TargetPosition.FLAT, "test")
    with pytest.raises(BenchmarkCompilationError, match="maximum order"):
        compile_signals(
            (valid, flip, final_flat),
            candles,
            tiny_maximum,
            sizing,
            max_bar_participation=Decimal("1"),
        )
    high_minimum = replace(instrument, min_notional=Decimal("1000000"))
    with pytest.raises(BenchmarkCompilationError, match="minimum notional"):
        compile_signals(
            (valid, flat),
            candles,
            high_minimum,
            sizing,
            max_bar_participation=Decimal("1"),
        )


def test_runner_and_distribution_without_registry() -> None:
    candles, instrument = _synthetic_market()
    runner = BenchmarkRunner(
        dataset_version="DS-TEST",
        candles=candles,
        instrument=instrument,
        initial_cash=Decimal("10000"),
        sizing=FixedQuantityPolicy(Decimal("1")),
        assumptions=ExecutionAssumptions(max_bar_participation=Decimal("0.05")),
    )
    suite = runner.run_suite(random_seeds=20)
    assert len(suite.deterministic) == 3
    assert suite.random_net_returns.runs == 20
    assert all(item.experiment_id is None for item in suite.random)
    with pytest.raises(ValueError, match="at least 20"):
        runner.run_suite(random_seeds=19)
    with pytest.raises(ValueError, match="non-empty"):
        BenchmarkRunner(
            dataset_version="DS-TEST",
            candles=(),
            instrument=instrument,
            initial_cash=Decimal("10000"),
            sizing=FixedQuantityPolicy(Decimal("1")),
        )


def test_distribution_nearest_rank_and_empty_rejection() -> None:
    result = summarize_distribution(tuple(Decimal(index) for index in range(1, 101)))
    assert result.minimum == 1
    assert result.p05 == 6
    assert result.median == 51
    assert result.p95 == 95
    assert result.maximum == 100
    assert result.mean == Decimal("50.5")
    with pytest.raises(ValueError, match="required"):
        summarize_distribution(())


def test_full_smoke_persists_every_path(tmp_path: Path) -> None:
    payload = benchmark_smoke_payload(tmp_path)
    assert payload["status"] == "PASS"
    assert payload["experiments_recorded"] == 103
    assert payload["verdict"] == "INCONCLUSIVE"
    assert payload["live_trading"] == "BLOCKED"


def test_constant_market_generates_no_mean_reversion_signal() -> None:
    candles, _instrument = _synthetic_market()
    constant = tuple(
        replace(
            item,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
        )
        for item in candles
    )
    assert SimpleMeanReversion().generate(constant) == ()


def test_short_window_can_generate_no_trend_signal() -> None:
    candles, _instrument = _synthetic_market()
    assert SimpleTrendFollowing(50).generate(candles[:10]) == ()


def test_controls_cover_long_short_exit_and_window_flattening() -> None:
    candles, _instrument = _synthetic_market()
    prices = (100, 100, 110, 110, 90, 90, 100, 100, 115, 115)
    shaped = tuple(
        replace(
            candle,
            open=Decimal(price),
            high=Decimal(price + 1),
            low=Decimal(price - 1),
            close=Decimal(price),
        )
        for candle, price in zip(candles[: len(prices)], prices, strict=True)
    )
    trend = SimpleTrendFollowing(2).generate(shaped)
    assert {item.target for item in trend} >= {
        TargetPosition.LONG,
        TargetPosition.SHORT,
        TargetPosition.FLAT,
    }
    reversion = SimpleMeanReversion(3, Decimal("1")).generate(shaped)
    assert reversion
    assert reversion[-1].target is TargetPosition.FLAT
