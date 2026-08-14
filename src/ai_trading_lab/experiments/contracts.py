"""Contracts for reproducible experiment registration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ResearchVerdict(StrEnum):
    """Explicit research conclusion; never inferred from profit alone."""

    PASSED = "PASSED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ExperimentStatus(StrEnum):
    """Durable registry lifecycle."""

    RESERVED = "RESERVED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """Researcher-supplied identity and decision context."""

    git_commit: str
    hypothesis_id: str
    strategy_version: str
    parameters: tuple[tuple[str, str], ...]
    verdict: ResearchVerdict
    decision_reason: str


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    """One durable registry row and its immutable artifact directory."""

    experiment_id: str
    status: ExperimentStatus
    created_at: datetime
    completed_at: datetime | None
    git_commit: str
    dataset_version: str
    backtest_run_id: str
    verdict: ResearchVerdict
    artifact_path: Path | None
    artifact_sha256: str | None
    error: str | None
