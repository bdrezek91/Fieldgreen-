"""Compatibility exports for the shared PHASE 6 signal compiler."""

from ai_trading_lab.signals.compiler import SignalCompilationError, compile_signals

BenchmarkCompilationError = SignalCompilationError

__all__ = ["BenchmarkCompilationError", "compile_signals"]
