"""Frozen PHASE 6 hypothesis, matrix and family-advancement rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from ai_trading_lab.data.contracts import Timeframe

STRATEGY_GATE_VERSION = "strategy-family-gate-v1"
VALIDATION_INITIAL_CASH = Decimal("100000")
VALIDATION_FIXED_QUANTITIES = (
    ("BTCUSDT", Decimal("0.1")),
    ("ETHUSDT", Decimal("1")),
    ("SOLUSDT", Decimal("10")),
)
EXPECTED_VALIDATION_CELLS = frozenset(
    (symbol, timeframe)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    for timeframe in (Timeframe.ONE_HOUR, Timeframe.FOUR_HOURS)
)


class EvidenceKind(StrEnum):
    """Origin of evidence supplied to a family decision."""

    CURATED_BYBIT = "CURATED_BYBIT"
    SYNTHETIC = "SYNTHETIC"


class FamilyDecision(StrEnum):
    """PHASE 6 outcome; advancement is not proof of production edge."""

    ADVANCE_TO_PHASE_7 = "ADVANCE_TO_PHASE_7"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class ResearchWindow:
    """Chronological half-open interval with an explicit role."""

    name: str
    start: date
    end: date
    sealed: bool

    def __post_init__(self) -> None:
        if not self.name.strip() or self.start >= self.end:
            raise ValueError("research window requires a name and increasing dates")


@dataclass(frozen=True, slots=True)
class StrategyResearchProtocol:
    """Pre-result protocol for the first candidate family."""

    hypothesis_id: str
    hypothesis: str
    primary_metric: str
    symbols: tuple[str, ...]
    timeframes: tuple[Timeframe, ...]
    windows: tuple[ResearchWindow, ...]
    minimum_total_trades: int
    required_cell_passes: int
    funding_required: bool
    version: str = STRATEGY_GATE_VERSION

    def __post_init__(self) -> None:
        if (
            not self.hypothesis_id.strip()
            or not self.hypothesis.strip()
            or not self.primary_metric.strip()
            or not self.version.strip()
        ):
            raise ValueError("protocol identifiers and hypothesis cannot be empty")
        if not self.symbols or not self.timeframes or not self.windows:
            raise ValueError("protocol matrix and windows cannot be empty")
        if self.minimum_total_trades <= 0 or self.required_cell_passes <= 0:
            raise ValueError("protocol thresholds must be positive")


RESEARCH_PROTOCOL = StrategyResearchProtocol(
    hypothesis_id="HYP-TREND-DUAL-CHANNEL-001",
    hypothesis=(
        "Strong directional breakouts persist through delayed market reaction, while loss of a "
        "shorter price channel identifies decay before a full opposite breakout."
    ),
    primary_metric="median_net_return_across_validation_matrix",
    symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    timeframes=(Timeframe.ONE_HOUR, Timeframe.FOUR_HOURS),
    windows=(
        ResearchWindow("TRAIN", date(2022, 1, 1), date(2024, 1, 1), False),
        ResearchWindow("VALIDATION", date(2024, 1, 1), date(2025, 1, 1), False),
        ResearchWindow("TEST", date(2025, 1, 1), date(2026, 1, 1), True),
    ),
    minimum_total_trades=60,
    required_cell_passes=4,
    funding_required=True,
)


@dataclass(frozen=True, slots=True)
class ValidationCell:
    """Comparable validation evidence for one symbol/timeframe cell."""

    symbol: str
    timeframe: Timeframe
    window_name: str
    dataset_version: str
    assumptions_version: str
    funding_included: bool
    candidate_net_return: Decimal
    trend_net_return: Decimal
    random_p95_net_return: Decimal
    candidate_max_drawdown: Decimal
    trend_max_drawdown: Decimal
    candidate_trades: int


@dataclass(frozen=True, slots=True)
class FamilyAssessment:
    """Deterministic application of the frozen family gate."""

    decision: FamilyDecision
    reason: str
    cells: int
    total_trades: int
    positive_cells: int
    trend_beats: int
    random_p95_beats: int
    median_candidate_return: Decimal | None
    median_trend_return: Decimal | None
    median_candidate_drawdown: Decimal | None


def assess_validation(
    cells: tuple[ValidationCell, ...], evidence_kind: EvidenceKind
) -> FamilyAssessment:
    """Apply the immutable Phase 6 validation gate without touching sealed TEST data."""
    if evidence_kind is not EvidenceKind.CURATED_BYBIT:
        return _assessment(
            FamilyDecision.INCONCLUSIVE,
            "Synthetic evidence cannot evaluate edge.",
            cells,
        )
    identities = {(item.symbol, item.timeframe) for item in cells}
    if len(identities) != len(cells) or identities != EXPECTED_VALIDATION_CELLS:
        return _assessment(
            FamilyDecision.INCONCLUSIVE,
            "The complete predefined validation matrix is required.",
            cells,
        )
    if any(
        item.window_name != "VALIDATION"
        or not item.dataset_version.strip()
        or not item.funding_included
        for item in cells
    ):
        return _assessment(
            FamilyDecision.INCONCLUSIVE,
            "Every cell requires versioned VALIDATION data with historical funding.",
            cells,
        )
    assumption_versions = {item.assumptions_version for item in cells}
    if len(assumption_versions) != 1 or not next(iter(assumption_versions)).strip():
        return _assessment(
            FamilyDecision.INCONCLUSIVE,
            "Every cell must use the same versioned execution assumptions.",
            cells,
        )
    if any(item.candidate_trades < 0 for item in cells):
        raise ValueError("trade counts cannot be negative")
    if any(item.candidate_max_drawdown < 0 or item.trend_max_drawdown < 0 for item in cells):
        raise ValueError("drawdowns cannot be negative")
    assessment = _assessment(FamilyDecision.REJECTED, "Validation criteria were not met.", cells)
    if assessment.total_trades < RESEARCH_PROTOCOL.minimum_total_trades:
        return _assessment(
            FamilyDecision.INCONCLUSIVE,
            "Activity is below the predefined minimum total trade count.",
            cells,
        )
    median_trend_drawdown = _median(tuple(item.trend_max_drawdown for item in cells)) or Decimal(0)
    drawdown_limit = max(Decimal("0.20"), median_trend_drawdown * Decimal("1.25"))
    candidate_drawdown = assessment.median_candidate_drawdown
    passed = (
        assessment.positive_cells >= RESEARCH_PROTOCOL.required_cell_passes
        and assessment.trend_beats >= RESEARCH_PROTOCOL.required_cell_passes
        and assessment.random_p95_beats >= RESEARCH_PROTOCOL.required_cell_passes
        and (assessment.median_candidate_return or Decimal(0))
        > (assessment.median_trend_return or Decimal(0))
        and candidate_drawdown is not None
        and candidate_drawdown <= drawdown_limit
    )
    if passed:
        return _assessment(
            FamilyDecision.ADVANCE_TO_PHASE_7,
            "Frozen validation gate passed; TEST remains sealed and robustness is still required.",
            cells,
        )
    return assessment


def _assessment(
    decision: FamilyDecision, reason: str, cells: tuple[ValidationCell, ...]
) -> FamilyAssessment:
    candidate_returns = tuple(item.candidate_net_return for item in cells)
    return FamilyAssessment(
        decision=decision,
        reason=reason,
        cells=len(cells),
        total_trades=sum(item.candidate_trades for item in cells),
        positive_cells=sum(item.candidate_net_return > 0 for item in cells),
        trend_beats=sum(item.candidate_net_return > item.trend_net_return for item in cells),
        random_p95_beats=sum(
            item.candidate_net_return > item.random_p95_net_return for item in cells
        ),
        median_candidate_return=_median(candidate_returns),
        median_trend_return=_median(tuple(item.trend_net_return for item in cells)),
        median_candidate_drawdown=_median(tuple(item.candidate_max_drawdown for item in cells)),
    )


def _median(values: tuple[Decimal, ...]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)
