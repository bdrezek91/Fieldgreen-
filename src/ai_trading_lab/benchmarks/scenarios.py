"""Offline PHASE 5 suite smoke with synthetic data and no edge claim."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ai_trading_lab.backtesting.contracts import ExecutionAssumptions
from ai_trading_lab.benchmarks.contracts import FixedQuantityPolicy
from ai_trading_lab.benchmarks.runner import BenchmarkRunner
from ai_trading_lab.data.contracts import Candle, Instrument, Timeframe


def benchmark_smoke_payload(root: Path, *, git_commit: str = "0" * 40) -> dict[str, object]:
    """Persist all four controls and a 100-seed Random Entry distribution."""
    candles, instrument = _synthetic_market()
    suite = BenchmarkRunner(
        dataset_version="DS-PHASE-5-SYNTHETIC-V1",
        candles=candles,
        instrument=instrument,
        initial_cash=Decimal("10000"),
        sizing=FixedQuantityPolicy(Decimal("1")),
        assumptions=ExecutionAssumptions(
            maker_fee_rate=Decimal("0.0002"),
            taker_fee_rate=Decimal("0.00055"),
            half_spread_bps=Decimal("0.5"),
            market_slippage_bps=Decimal("1.0"),
            max_bar_participation=Decimal("0.05"),
        ),
        artifact_root=root,
        git_commit=git_commit,
    ).run_suite()
    deterministic = {
        item.name: {
            "experiment_id": item.experiment_id,
            "net_return": str(item.analytics.metrics.net_return),
            "trades": item.analytics.metrics.trades,
        }
        for item in suite.deterministic
    }
    distribution = suite.random_net_returns
    return {
        "status": "PASS",
        "policy_version": suite.policy_version,
        "dataset_version": "DS-PHASE-5-SYNTHETIC-V1",
        "deterministic": deterministic,
        "random_entry": {
            "runs": distribution.runs,
            "first_experiment_id": suite.random[0].experiment_id,
            "last_experiment_id": suite.random[-1].experiment_id,
            "min_net_return": str(distribution.minimum),
            "p05_net_return": str(distribution.p05),
            "median_net_return": str(distribution.median),
            "mean_net_return": str(distribution.mean),
            "p95_net_return": str(distribution.p95),
            "max_net_return": str(distribution.maximum),
        },
        "experiments_recorded": len(suite.deterministic) + len(suite.random),
        "verdict": "INCONCLUSIVE",
        "live_trading": "BLOCKED",
    }


def _synthetic_market() -> tuple[tuple[Candle, ...], Instrument]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index in range(240):
        cycle = Decimal((index % 10) - 5) * Decimal("0.10")
        if index < 60:
            close = Decimal("100") + cycle
        elif index < 120:
            close = Decimal("100") + Decimal(index - 60) * Decimal("0.50") + cycle
        elif index < 180:
            close = Decimal("130") - Decimal(index - 120) * Decimal("0.80") + cycle
        else:
            close = Decimal("82") + Decimal(index - 180) * Decimal("0.60") + cycle
        if index == 35:
            close += Decimal("8")
        elif index == 45:
            close -= Decimal("8")
        open_price = close - Decimal("0.10")
        candles.append(
            Candle(
                symbol="BTCUSDT",
                timeframe=Timeframe.ONE_HOUR,
                open_time=start + timedelta(hours=index),
                open=open_price,
                high=max(open_price, close) + Decimal("0.60"),
                low=min(open_price, close) - Decimal("0.60"),
                close=close,
                volume=Decimal("1000"),
                turnover=close * Decimal("1000"),
                source="synthetic_phase_5_smoke",
            )
        )
    instrument = Instrument(
        symbol="BTCUSDT",
        base_coin="BTC",
        quote_coin="USDT",
        settle_coin="USDT",
        status="Trading",
        contract_type="LinearPerpetual",
        launch_time=datetime(2020, 1, 1, tzinfo=UTC),
        delivery_time=None,
        tick_size=Decimal("0.1"),
        min_price=Decimal("0.1"),
        max_price=Decimal("1000000"),
        quantity_step=Decimal("0.001"),
        min_order_quantity=Decimal("0.001"),
        max_order_quantity=Decimal("1000"),
        min_notional=Decimal("1"),
        min_leverage=Decimal("1"),
        max_leverage=Decimal("100"),
        leverage_step=Decimal("0.01"),
        funding_interval_minutes=480,
        source="synthetic_phase_5_smoke",
    )
    return tuple(candles), instrument
