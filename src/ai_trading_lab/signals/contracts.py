"""Framework-neutral signal contracts shared by controls and candidate strategies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
class PositionSignal:
    """Point-in-time target generated only from information closed by `generated_at`."""

    symbol: str
    generated_at: datetime
    target: TargetPosition
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.reason.strip():
            raise ValueError("signal symbol and reason are required")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("signal timestamp must be timezone-aware")


class SignalStrategy(Protocol):
    """Owned port implemented by controls and candidate strategies."""

    @property
    def name(self) -> str:
        """Return a stable strategy name."""

    @property
    def version(self) -> str:
        """Return a frozen implementation version."""

    @property
    def parameters(self) -> tuple[tuple[str, str], ...]:
        """Return every fixed parameter as reproducibility evidence."""

    def generate(self, candles: tuple[Candle, ...]) -> tuple[PositionSignal, ...]:
        """Generate target changes from chronologically closed candles."""
