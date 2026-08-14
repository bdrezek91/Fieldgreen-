"""Owned contracts for PHASE 5 benchmark signals and comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from ai_trading_lab.data.contracts import Candle


class TargetPosition(StrEnum):
    """Desired net direction, without exchange or sizing concerns."""

    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def units(self) -> int:
        """Return the signed unit representation used by the compiler."""
        return {TargetPosition.FLAT: 0, TargetPosition.LONG: 1, TargetPosition.SHORT: -1}[self]


@dataclass(frozen=True, slots=True)
class BenchmarkSignal:
    """A point-in-time target generated only from information closed by `generated_at`."""

    symbol: str
    generated_at: datetime
    target: TargetPosition
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.reason.strip():
            raise ValueError("signal symbol and reason are required")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("signal timestamp must be timezone-aware")


class BenchmarkStrategy(Protocol):
    """Framework-neutral benchmark strategy port."""

    @property
    def name(self) -> str:
        """Return a stable benchmark name."""

    @property
    def version(self) -> str:
        """Return a frozen implementation version."""

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        """Return every fixed parameter as reproducibility evidence."""

    def generate(self, candles: tuple[Candle, ...]) -> tuple[BenchmarkSignal, ...]:
        """Generate target changes from chronologically closed candles."""


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
