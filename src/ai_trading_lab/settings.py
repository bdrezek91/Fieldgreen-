"""Fail-closed application settings for the pre-live project phases."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

MODE_ENV: Final = "ATL_MODE"
LOG_LEVEL_ENV: Final = "ATL_LOG_LEVEL"
DATA_ROOT_ENV: Final = "ATL_DATA_ROOT"
ALLOWED_LOG_LEVELS: Final = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class LiveModeBlockedError(ValueError):
    """Raised whenever configuration attempts to enable live trading."""


class RunMode(StrEnum):
    """Modes allowed before a separately approved PHASE 15 implementation."""

    RESEARCH = "RESEARCH"
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"

    @classmethod
    def parse(cls, raw_value: str) -> RunMode:
        """Parse a mode while treating LIVE as an explicit safety violation."""
        normalized = raw_value.strip().upper()
        if normalized == "LIVE":
            raise LiveModeBlockedError("LIVE mode is hard-blocked until PHASE 15 approval")
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(mode.value for mode in cls)
            raise ValueError(f"Unsupported ATL_MODE={raw_value!r}; allowed: {allowed}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    """Pre-live settings with no credentials or private exchange configuration."""

    mode: RunMode = RunMode.RESEARCH
    log_level: str = "INFO"
    data_root: Path = Path("data")

    def __post_init__(self) -> None:
        normalized_log_level = self.log_level.strip().upper()
        if normalized_log_level not in ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(ALLOWED_LOG_LEVELS))
            raise ValueError(f"Unsupported log level {self.log_level!r}; allowed: {allowed}")
        object.__setattr__(self, "log_level", normalized_log_level)
        if self.data_root == Path("."):
            raise ValueError("data_root cannot be the current directory")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Load only safe pre-live settings from an environment mapping."""
        source = os.environ if environ is None else environ
        return cls(
            mode=RunMode.parse(source.get(MODE_ENV, RunMode.RESEARCH.value)),
            log_level=source.get(LOG_LEVEL_ENV, "INFO"),
            data_root=Path(source.get(DATA_ROOT_ENV, "data")),
        )

    def public_status(self) -> dict[str, str | list[str]]:
        """Return an intentionally credential-free status representation."""
        return {
            "mode": self.mode.value,
            "log_level": self.log_level,
            "allowed_modes": [mode.value for mode in RunMode],
            "live_trading": "BLOCKED",
            "data_root": str(self.data_root),
        }
