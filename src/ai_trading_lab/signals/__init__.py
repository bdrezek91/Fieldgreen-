"""Owned signal boundary independent of strategy, risk and execution engines."""

from ai_trading_lab.signals.compiler import SignalCompilationError, compile_signals
from ai_trading_lab.signals.contracts import PositionSignal, SignalStrategy, TargetPosition

__all__ = [
    "PositionSignal",
    "SignalCompilationError",
    "SignalStrategy",
    "TargetPosition",
    "compile_signals",
]
