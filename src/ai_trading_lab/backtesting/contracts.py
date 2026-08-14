"""Stable domain contracts for event-driven backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from ai_trading_lab.data.contracts import Candle, Instrument


class Side(StrEnum):
    """Order direction."""

    BUY = "BUY"
    SELL = "SELL"

    @property
    def sign(self) -> Decimal:
        """Return +1 for buy and -1 for sell."""
        return Decimal(1) if self is Side.BUY else Decimal(-1)


class OrderType(StrEnum):
    """Order types supported by the T1 reference kernel."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"


class TimeInForce(StrEnum):
    """Supported time-in-force values."""

    GTC = "GTC"
    IOC = "IOC"


class LiquidityRole(StrEnum):
    """Fee classification of an execution."""

    MAKER = "MAKER"
    TAKER = "TAKER"
    LIQUIDATION = "LIQUIDATION"


class LimitFillPolicy(StrEnum):
    """Eligibility rule when a bar only touches a resting limit."""

    CROSS_ONLY = "CROSS_ONLY"
    TOUCH = "TOUCH"


class IntrabarPolicy(StrEnum):
    """Resolution for multiple protective orders reached in one bar."""

    WORST_CASE = "WORST_CASE"


class LiquidationModel(StrEnum):
    """Liquidation fidelity declared by the run."""

    DISABLED = "DISABLED"
    APPROXIMATE = "APPROXIMATE"


class LedgerEventType(StrEnum):
    """Canonical audit-ledger event types."""

    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELED = "ORDER_CANCELED"
    ORDER_FILLED = "ORDER_FILLED"
    FUNDING_SETTLED = "FUNDING_SETTLED"
    MARK_UPDATED = "MARK_UPDATED"
    LIQUIDATED = "LIQUIDATED"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Venue-neutral instruction created outside the backtest engine."""

    client_order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    submitted_at: datetime
    limit_price: Decimal | None = None
    trigger_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    oco_group: str | None = None


@dataclass(frozen=True, slots=True)
class FundingEvent:
    """Historical perpetual funding settlement input."""

    symbol: str
    timestamp: datetime
    rate: Decimal
    mark_price: Decimal


@dataclass(frozen=True, slots=True)
class MarkPriceEvent:
    """Point-in-time mark price used for PnL and liquidation checks."""

    symbol: str
    timestamp: datetime
    price: Decimal


@dataclass(frozen=True, slots=True)
class ExecutionAssumptions:
    """Versioned execution and margin assumptions for one run."""

    maker_fee_rate: Decimal = Decimal("0.0002")
    taker_fee_rate: Decimal = Decimal("0.00055")
    half_spread_bps: Decimal = Decimal("0.5")
    market_slippage_bps: Decimal = Decimal("1.0")
    max_bar_participation: Decimal = Decimal("0.05")
    limit_fill_policy: LimitFillPolicy = LimitFillPolicy.CROSS_ONLY
    intrabar_policy: IntrabarPolicy = IntrabarPolicy.WORST_CASE
    leverage: Decimal = Decimal(1)
    maintenance_margin_rate: Decimal = Decimal("0.005")
    liquidation_buffer_rate: Decimal = Decimal("0.001")
    liquidation_fee_rate: Decimal = Decimal("0.005")
    liquidation_model: LiquidationModel = LiquidationModel.DISABLED
    random_seed: int = 0
    latency_milliseconds: int = 0
    version: str = "execution-assumptions-v1"

    def __post_init__(self) -> None:
        rates = (
            self.maker_fee_rate,
            self.taker_fee_rate,
            self.half_spread_bps,
            self.market_slippage_bps,
            self.maintenance_margin_rate,
            self.liquidation_buffer_rate,
            self.liquidation_fee_rate,
        )
        if any(value < 0 for value in rates):
            raise ValueError("execution rates cannot be negative")
        if not Decimal(0) < self.max_bar_participation <= Decimal(1):
            raise ValueError("max_bar_participation must be in (0, 1]")
        if self.leverage < 1:
            raise ValueError("leverage must be at least one")
        if self.latency_milliseconds < 0:
            raise ValueError("latency_milliseconds cannot be negative")
        if not self.version.strip():
            raise ValueError("assumption version cannot be empty")


@dataclass(frozen=True, slots=True)
class BacktestRequest:
    """Complete deterministic input to a backtest run."""

    dataset_version: str
    candles: tuple[Candle, ...]
    instruments: tuple[Instrument, ...]
    orders: tuple[OrderIntent, ...]
    initial_cash: Decimal
    assumptions: ExecutionAssumptions = ExecutionAssumptions()
    funding: tuple[FundingEvent, ...] = ()
    marks: tuple[MarkPriceEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class Fill:
    """One canonical execution record."""

    fill_id: str
    client_order_id: str
    symbol: str
    side: Side
    timestamp: datetime
    quantity: Decimal
    price: Decimal
    liquidity: LiquidityRole
    fee: Decimal


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    """Deterministically ordered audit event."""

    sequence: int
    timestamp: datetime
    event_type: LedgerEventType
    symbol: str
    client_order_id: str | None
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Final net position state for one symbol."""

    symbol: str
    quantity: Decimal
    average_price: Decimal | None
    realized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Portfolio valuation at a point in simulated time."""

    timestamp: datetime
    cash: Decimal
    unrealized_pnl: Decimal
    equity: Decimal


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Canonical result independent of the execution kernel implementation."""

    run_id: str
    dataset_version: str
    engine_version: str
    assumptions_version: str
    initial_cash: Decimal
    final_cash: Decimal
    final_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    total_funding: Decimal
    liquidation_count: int
    paper_eligible: bool
    fills: tuple[Fill, ...]
    ledger: tuple[LedgerEvent, ...]
    positions: tuple[PositionSnapshot, ...]
    equity_curve: tuple[EquityPoint, ...]


class BacktestEngine(Protocol):
    """Replaceable engine port owned by the project domain."""

    def run(self, request: BacktestRequest) -> BacktestResult:
        """Execute a deterministic backtest and return a canonical result."""
