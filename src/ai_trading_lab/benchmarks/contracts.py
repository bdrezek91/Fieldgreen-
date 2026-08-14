"""Owned contracts for PHASE 5 benchmark signals and comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trading_lab.signals.contracts import PositionSignal as BenchmarkSignal
from ai_trading_lab.signals.contracts import SignalStrategy as BenchmarkStrategy
from ai_trading_lab.signals.contracts import TargetPosition

__all__ = [
    "BenchmarkSignal",
    "BenchmarkStrategy",
    "DistributionSummary",
    "FixedQuantityPolicy",
    "TargetPosition",
]


@dataclass(frozen=True, slots=True)
class FixedQuantityPolicy:
    """PHASE 5 comparison sizing; not the future portfolio risk engine."""

    quantity: Decimal
    version: str = "fixed-quantity-v1"

    def __post_init__(self) -> None:
        if self.quantity <= 0 or not self.version.strip():
            raise ValueError("fixed quantity and policy version must be valid")


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    """Frozen descriptive summary for many seeded Random Entry paths."""

    runs: int
    minimum: Decimal
    p05: Decimal
    median: Decimal
    mean: Decimal
    p95: Decimal
    maximum: Decimal
