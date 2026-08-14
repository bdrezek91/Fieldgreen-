"""Candidate strategy families; none is authorized for paper or live execution."""

from ai_trading_lab.strategies.contracts import (
    EXPECTED_VALIDATION_CELLS,
    RESEARCH_PROTOCOL,
    STRATEGY_GATE_VERSION,
    EvidenceKind,
    FamilyAssessment,
    FamilyDecision,
    StrategyResearchProtocol,
    ValidationCell,
    assess_validation,
)
from ai_trading_lab.strategies.runner import CandidateRun, CandidateRunner
from ai_trading_lab.strategies.trend import DualChannelTrend

__all__ = [
    "EXPECTED_VALIDATION_CELLS",
    "RESEARCH_PROTOCOL",
    "STRATEGY_GATE_VERSION",
    "CandidateRun",
    "CandidateRunner",
    "DualChannelTrend",
    "EvidenceKind",
    "FamilyAssessment",
    "FamilyDecision",
    "StrategyResearchProtocol",
    "ValidationCell",
    "assess_validation",
]
