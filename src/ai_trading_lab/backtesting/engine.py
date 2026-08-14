"""Conservative deterministic T1 bar-event reference backtester."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import IntEnum

from ai_trading_lab.backtesting.contracts import (
    BacktestRequest,
    BacktestResult,
    EquityPoint,
    Fill,
    FundingEvent,
    LedgerEvent,
    LedgerEventType,
    LimitFillPolicy,
    LiquidationModel,
    LiquidityRole,
    MarkPriceEvent,
    OrderIntent,
    OrderType,
    PositionSnapshot,
    Side,
    TimeInForce,
)
from ai_trading_lab.data.contracts import Candle, Instrument
from ai_trading_lab.data.validation import CandleValidator

ENGINE_VERSION = "reference-bar-engine-v1"
BPS = Decimal("10000")


class BacktestConfigurationError(ValueError):
    """Raised when a run would have ambiguous or invalid semantics."""


class _EventPriority(IntEnum):
    FUNDING = 0
    MARK = 1
    BAR = 2


@dataclass(slots=True)
class _WorkingOrder:
    intent: OrderIntent
    remaining: Decimal
    closed: bool = False


@dataclass(frozen=True, slots=True)
class _Candidate:
    order: _WorkingOrder
    raw_price: Decimal
    liquidity: LiquidityRole


@dataclass(slots=True)
class _Position:
    symbol: str
    quantity: Decimal = Decimal(0)
    average_price: Decimal | None = None
    realized_pnl: Decimal = Decimal(0)

    def apply(self, side: Side, quantity: Decimal, price: Decimal) -> Decimal:
        signed = quantity * side.sign
        old_quantity = self.quantity
        old_average = self.average_price
        realized = Decimal(0)
        if old_quantity == 0 or old_quantity * signed > 0:
            old_notional = abs(old_quantity) * (old_average or Decimal(0))
            new_quantity = old_quantity + signed
            self.average_price = (old_notional + quantity * price) / abs(new_quantity)
            self.quantity = new_quantity
            return realized

        closing = min(abs(old_quantity), quantity)
        direction = Decimal(1) if old_quantity > 0 else Decimal(-1)
        realized = closing * (price - (old_average or price)) * direction
        new_quantity = old_quantity + signed
        self.quantity = new_quantity
        self.realized_pnl += realized
        if new_quantity == 0:
            self.average_price = None
        elif old_quantity * new_quantity < 0:
            self.average_price = price
        return realized


@dataclass(slots=True)
class _State:
    cash: Decimal
    positions: dict[str, _Position]
    last_prices: dict[str, Decimal]
    fills: list[Fill]
    pending_ledger: list[
        tuple[datetime, int, LedgerEventType, str, str | None, tuple[tuple[str, str], ...]]
    ]
    equity_curve: list[EquityPoint]
    total_fees: Decimal = Decimal(0)
    total_funding: Decimal = Decimal(0)
    liquidation_count: int = 0
    ordinal: int = 0


class ReferenceBarBacktestEngine:
    """Owned reference kernel with explicit conservative bar semantics."""

    def run(self, request: BacktestRequest) -> BacktestResult:
        """Run scheduled order intents against bars, funding and mark events."""
        instruments = self._validate_request(request)
        state = _State(
            cash=request.initial_cash,
            positions={symbol: _Position(symbol) for symbol in instruments},
            last_prices={},
            fills=[],
            pending_ledger=[],
            equity_curve=[],
        )
        orders = self._prepare_orders(request, instruments, state)
        events = self._events(request)
        for _timestamp, _priority, _symbol, event in events:
            if isinstance(event, FundingEvent):
                self._apply_funding(event, state)
            elif isinstance(event, MarkPriceEvent):
                self._apply_mark(event, request, instruments, orders, state)
            else:
                self._apply_bar(event, request, instruments, orders, state)

        final_time = max(item.close_time for item in request.candles)
        final_equity = self._record_equity(final_time, state, append=False).equity
        ledger = self._finalize_ledger(state)
        positions = tuple(
            PositionSnapshot(item.symbol, item.quantity, item.average_price, item.realized_pnl)
            for item in sorted(state.positions.values(), key=lambda value: value.symbol)
        )
        realized = sum((item.realized_pnl for item in state.positions.values()), start=Decimal(0))
        unrealized = final_equity - state.cash
        return BacktestResult(
            run_id=_run_id(request),
            dataset_version=request.dataset_version,
            engine_version=ENGINE_VERSION,
            assumptions_version=request.assumptions.version,
            initial_cash=request.initial_cash,
            final_cash=state.cash,
            final_equity=final_equity,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_fees=state.total_fees,
            total_funding=state.total_funding,
            liquidation_count=state.liquidation_count,
            paper_eligible=request.assumptions.leverage == 1,
            fills=tuple(state.fills),
            ledger=ledger,
            positions=positions,
            equity_curve=tuple(sorted(state.equity_curve, key=lambda point: point.timestamp)),
        )

    def _validate_request(self, request: BacktestRequest) -> dict[str, Instrument]:
        if not request.dataset_version.strip():
            raise BacktestConfigurationError("dataset_version is required")
        if request.initial_cash <= 0:
            raise BacktestConfigurationError("initial_cash must be positive")
        instruments = {item.symbol: item for item in request.instruments}
        if len(instruments) != len(request.instruments) or not instruments:
            raise BacktestConfigurationError("instruments must be non-empty and unique")
        if request.assumptions.leverage > min(item.max_leverage for item in instruments.values()):
            raise BacktestConfigurationError("configured leverage exceeds instrument maximum")
        bars_by_symbol: dict[str, list[Candle]] = {}
        for candle in request.candles:
            if candle.symbol not in instruments:
                raise BacktestConfigurationError(f"missing instrument for {candle.symbol}")
            bars_by_symbol.setdefault(candle.symbol, []).append(candle)
        if not bars_by_symbol:
            raise BacktestConfigurationError("candles are required")
        for rows in bars_by_symbol.values():
            ordered = tuple(sorted(rows, key=lambda item: item.open_time))
            report = CandleValidator().validate(ordered, as_of=ordered[-1].close_time)
            if not report.is_valid:
                codes = ", ".join(sorted({issue.code for issue in report.issues}))
                raise BacktestConfigurationError(f"invalid candle input: {codes}")
        opens = {(item.symbol, item.open_time) for item in request.candles}
        for funding_event in request.funding:
            if (
                funding_event.symbol not in instruments
                or (
                    funding_event.symbol,
                    funding_event.timestamp,
                )
                not in opens
            ):
                raise BacktestConfigurationError(
                    "funding and mark events must align with a known candle open"
                )
            if (
                funding_event.timestamp.tzinfo is None
                or funding_event.timestamp.utcoffset() is None
            ):
                raise BacktestConfigurationError("external event timestamp must be timezone-aware")
        for mark_event in request.marks:
            if (
                mark_event.symbol not in instruments
                or (
                    mark_event.symbol,
                    mark_event.timestamp,
                )
                not in opens
            ):
                raise BacktestConfigurationError(
                    "funding and mark events must align with a known candle open"
                )
            if mark_event.timestamp.tzinfo is None or mark_event.timestamp.utcoffset() is None:
                raise BacktestConfigurationError("external event timestamp must be timezone-aware")
        return instruments

    def _prepare_orders(
        self,
        request: BacktestRequest,
        instruments: dict[str, Instrument],
        state: _State,
    ) -> list[_WorkingOrder]:
        identifiers: set[str] = set()
        working: list[_WorkingOrder] = []
        for intent in sorted(request.orders, key=_order_sort_key):
            reason = self._order_rejection_reason(intent, instruments, identifiers)
            if reason is not None:
                self._ledger(
                    state,
                    intent.submitted_at,
                    LedgerEventType.ORDER_REJECTED,
                    intent.symbol,
                    intent.client_order_id,
                    (("reason", reason),),
                )
                continue
            identifiers.add(intent.client_order_id)
            working.append(_WorkingOrder(intent, intent.quantity))
            self._ledger(
                state,
                intent.submitted_at,
                LedgerEventType.ORDER_ACCEPTED,
                intent.symbol,
                intent.client_order_id,
            )
        return working

    @staticmethod
    def _order_rejection_reason(
        intent: OrderIntent,
        instruments: dict[str, Instrument],
        identifiers: set[str],
    ) -> str | None:
        if not intent.client_order_id.strip() or intent.client_order_id in identifiers:
            return "INVALID_OR_DUPLICATE_CLIENT_ORDER_ID"
        instrument = instruments.get(intent.symbol)
        if instrument is None:
            return "UNKNOWN_INSTRUMENT"
        if intent.submitted_at.tzinfo is None or intent.submitted_at.utcoffset() is None:
            return "NAIVE_SUBMISSION_TIME"
        if intent.quantity <= 0 or intent.quantity % instrument.quantity_step != 0:
            return "INVALID_QUANTITY_PRECISION"
        if intent.quantity < instrument.min_order_quantity:
            return "BELOW_MINIMUM_QUANTITY"
        if intent.quantity > instrument.max_order_quantity:
            return "ABOVE_MAXIMUM_QUANTITY"
        if intent.order_type is OrderType.LIMIT:
            if intent.limit_price is None or intent.limit_price % instrument.tick_size != 0:
                return "INVALID_LIMIT_PRICE"
        elif intent.limit_price is not None:
            return "UNEXPECTED_LIMIT_PRICE"
        if intent.order_type is OrderType.STOP_MARKET:
            if intent.trigger_price is None or intent.trigger_price % instrument.tick_size != 0:
                return "INVALID_TRIGGER_PRICE"
        elif intent.trigger_price is not None:
            return "UNEXPECTED_TRIGGER_PRICE"
        return None

    @staticmethod
    def _events(
        request: BacktestRequest,
    ) -> list[tuple[datetime, int, str, Candle | FundingEvent | MarkPriceEvent]]:
        events: list[tuple[datetime, int, str, Candle | FundingEvent | MarkPriceEvent]] = []
        events.extend(
            (item.timestamp, _EventPriority.FUNDING, item.symbol, item) for item in request.funding
        )
        events.extend(
            (item.timestamp, _EventPriority.MARK, item.symbol, item) for item in request.marks
        )
        events.extend(
            (item.open_time, _EventPriority.BAR, item.symbol, item) for item in request.candles
        )
        return sorted(events, key=lambda value: (value[0], value[1], value[2]))

    def _apply_bar(
        self,
        candle: Candle,
        request: BacktestRequest,
        instruments: dict[str, Instrument],
        orders: list[_WorkingOrder],
        state: _State,
    ) -> None:
        instrument = instruments[candle.symbol]
        available = _floor_step(
            candle.volume * request.assumptions.max_bar_participation,
            instrument.quantity_step,
        )
        candidates: list[_Candidate] = []
        for order in orders:
            if order.closed or order.intent.symbol != candle.symbol:
                continue
            active_at = order.intent.submitted_at + timedelta(
                milliseconds=request.assumptions.latency_milliseconds
            )
            if active_at > candle.open_time:
                continue
            candidate = self._candidate(order, candle, request)
            if candidate is not None:
                candidates.append(candidate)
            elif order.intent.time_in_force is TimeInForce.IOC:
                self._cancel(order, candle.open_time, state, "IOC_NOT_FILLED")

        for candidate in self._resolve_oco(candidates, state):
            if available <= 0:
                break
            filled = self._fill_candidate(
                candidate, available, candle.open_time, request, instrument, state
            )
            available -= filled
            if filled > 0 and candidate.order.intent.oco_group:
                for sibling in orders:
                    if (
                        not sibling.closed
                        and sibling is not candidate.order
                        and sibling.intent.oco_group == candidate.order.intent.oco_group
                    ):
                        self._cancel(sibling, candle.open_time, state, "OCO_SIBLING_FILLED")
        state.last_prices[candle.symbol] = candle.close
        self._record_equity(candle.close_time, state)

    def _candidate(
        self, order: _WorkingOrder, candle: Candle, request: BacktestRequest
    ) -> _Candidate | None:
        intent = order.intent
        if intent.order_type is OrderType.MARKET:
            return _Candidate(order, candle.open, LiquidityRole.TAKER)
        if intent.order_type is OrderType.STOP_MARKET:
            trigger = intent.trigger_price or Decimal(0)
            if intent.side is Side.BUY:
                if candle.open >= trigger:
                    return _Candidate(order, candle.open, LiquidityRole.TAKER)
                if candle.high >= trigger:
                    return _Candidate(order, trigger, LiquidityRole.TAKER)
            else:
                if candle.open <= trigger:
                    return _Candidate(order, candle.open, LiquidityRole.TAKER)
                if candle.low <= trigger:
                    return _Candidate(order, trigger, LiquidityRole.TAKER)
            return None

        limit = intent.limit_price or Decimal(0)
        if intent.side is Side.BUY:
            if candle.open <= limit:
                return _Candidate(order, candle.open, LiquidityRole.TAKER)
            crossed = candle.low < limit
            touched = candle.low == limit
        else:
            if candle.open >= limit:
                return _Candidate(order, candle.open, LiquidityRole.TAKER)
            crossed = candle.high > limit
            touched = candle.high == limit
        if crossed or (touched and request.assumptions.limit_fill_policy is LimitFillPolicy.TOUCH):
            return _Candidate(order, limit, LiquidityRole.MAKER)
        return None

    @staticmethod
    def _resolve_oco(candidates: list[_Candidate], state: _State) -> list[_Candidate]:
        standalone = [item for item in candidates if item.order.intent.oco_group is None]
        groups: dict[str, list[_Candidate]] = {}
        for item in candidates:
            if item.order.intent.oco_group is not None:
                groups.setdefault(item.order.intent.oco_group, []).append(item)
        selected = sorted(standalone, key=lambda item: item.order.intent.client_order_id)
        for name in sorted(groups):
            group = groups[name]
            symbol = group[0].order.intent.symbol
            position = state.positions[symbol].quantity
            if position > 0:
                selected.append(min(group, key=lambda item: item.raw_price))
            elif position < 0:
                selected.append(max(group, key=lambda item: item.raw_price))
            else:
                selected.extend(sorted(group, key=lambda item: item.order.intent.client_order_id))
        return selected

    def _fill_candidate(
        self,
        candidate: _Candidate,
        available: Decimal,
        timestamp: datetime,
        request: BacktestRequest,
        instrument: Instrument,
        state: _State,
    ) -> Decimal:
        order = candidate.order
        quantity = min(order.remaining, available)
        position = state.positions[order.intent.symbol]
        if order.intent.reduce_only:
            if position.quantity == 0 or position.quantity * order.intent.side.sign > 0:
                self._cancel(order, timestamp, state, "REDUCE_ONLY_WOULD_INCREASE")
                return Decimal(0)
            quantity = min(quantity, abs(position.quantity))
        if quantity <= 0:
            return Decimal(0)
        price = self._execution_price(candidate, request, instrument)
        if quantity * price < instrument.min_notional:
            self._cancel(order, timestamp, state, "BELOW_MINIMUM_NOTIONAL")
            return Decimal(0)
        additional = self._additional_exposure(position, order.intent.side, quantity)
        if additional > 0 and not self._has_margin(additional, price, request, state):
            self._cancel(order, timestamp, state, "INSUFFICIENT_MARGIN")
            return Decimal(0)
        fee_rate = (
            request.assumptions.maker_fee_rate
            if candidate.liquidity is LiquidityRole.MAKER
            else request.assumptions.taker_fee_rate
        )
        self._execute(
            order.intent,
            quantity,
            price,
            candidate.liquidity,
            fee_rate,
            timestamp,
            state,
        )
        order.remaining -= quantity
        if order.remaining == 0 or order.intent.order_type is OrderType.MARKET:
            order.closed = True
            if order.remaining > 0:
                self._ledger(
                    state,
                    timestamp,
                    LedgerEventType.ORDER_CANCELED,
                    order.intent.symbol,
                    order.intent.client_order_id,
                    (("reason", "UNFILLED_MARKET_REMAINDER"),),
                )
        elif order.intent.time_in_force is TimeInForce.IOC:
            self._cancel(order, timestamp, state, "IOC_REMAINDER")
        return quantity

    @staticmethod
    def _execution_price(
        candidate: _Candidate, request: BacktestRequest, instrument: Instrument
    ) -> Decimal:
        if candidate.liquidity is LiquidityRole.MAKER:
            return candidate.raw_price
        bps = request.assumptions.half_spread_bps + request.assumptions.market_slippage_bps
        adjusted = candidate.raw_price * (Decimal(1) + candidate.order.intent.side.sign * bps / BPS)
        if candidate.order.intent.order_type is OrderType.LIMIT:
            limit = candidate.order.intent.limit_price or adjusted
            adjusted = (
                min(adjusted, limit)
                if candidate.order.intent.side is Side.BUY
                else max(adjusted, limit)
            )
        return _round_adverse(adjusted, instrument.tick_size, candidate.order.intent.side)

    @staticmethod
    def _additional_exposure(position: _Position, side: Side, quantity: Decimal) -> Decimal:
        if position.quantity == 0 or position.quantity * side.sign > 0:
            return quantity
        return max(quantity - abs(position.quantity), Decimal(0))

    def _has_margin(
        self,
        quantity: Decimal,
        price: Decimal,
        request: BacktestRequest,
        state: _State,
    ) -> bool:
        equity = self._equity(state)
        used = sum(
            (
                abs(position.quantity)
                * state.last_prices.get(symbol, position.average_price or Decimal(0))
                / request.assumptions.leverage
                for symbol, position in state.positions.items()
            ),
            start=Decimal(0),
        )
        required = quantity * price / request.assumptions.leverage
        return equity - used >= required

    def _execute(
        self,
        intent: OrderIntent,
        quantity: Decimal,
        price: Decimal,
        liquidity: LiquidityRole,
        fee_rate: Decimal,
        timestamp: datetime,
        state: _State,
    ) -> None:
        fee = quantity * price * fee_rate
        realized = state.positions[intent.symbol].apply(intent.side, quantity, price)
        state.cash += realized - fee
        state.total_fees += fee
        fill = Fill(
            fill_id=f"F-{len(state.fills) + 1:08d}",
            client_order_id=intent.client_order_id,
            symbol=intent.symbol,
            side=intent.side,
            timestamp=timestamp,
            quantity=quantity,
            price=price,
            liquidity=liquidity,
            fee=fee,
        )
        state.fills.append(fill)
        self._ledger(
            state,
            timestamp,
            LedgerEventType.ORDER_FILLED,
            intent.symbol,
            intent.client_order_id,
            (("fill_id", fill.fill_id), ("price", str(price)), ("quantity", str(quantity))),
        )

    def _apply_funding(self, event: FundingEvent, state: _State) -> None:
        position = state.positions[event.symbol]
        payment = -position.quantity * event.mark_price * event.rate
        state.cash += payment
        state.total_funding += payment
        state.last_prices[event.symbol] = event.mark_price
        self._ledger(
            state,
            event.timestamp,
            LedgerEventType.FUNDING_SETTLED,
            event.symbol,
            None,
            (("rate", str(event.rate)), ("payment", str(payment))),
        )
        self._record_equity(event.timestamp, state)

    def _apply_mark(
        self,
        event: MarkPriceEvent,
        request: BacktestRequest,
        instruments: dict[str, Instrument],
        orders: list[_WorkingOrder],
        state: _State,
    ) -> None:
        if event.price <= 0:
            raise BacktestConfigurationError("mark price must be positive")
        state.last_prices[event.symbol] = event.price
        self._ledger(
            state,
            event.timestamp,
            LedgerEventType.MARK_UPDATED,
            event.symbol,
            None,
            (("price", str(event.price)),),
        )
        if request.assumptions.liquidation_model is LiquidationModel.APPROXIMATE:
            self._check_liquidation(event, request, instruments[event.symbol], orders, state)
        self._record_equity(event.timestamp, state)

    def _check_liquidation(
        self,
        event: MarkPriceEvent,
        request: BacktestRequest,
        instrument: Instrument,
        orders: list[_WorkingOrder],
        state: _State,
    ) -> None:
        position = state.positions[event.symbol]
        if position.quantity == 0 or position.average_price is None:
            return
        rate = (
            Decimal(1) / request.assumptions.leverage
            - request.assumptions.maintenance_margin_rate
            - request.assumptions.liquidation_buffer_rate
        )
        if position.quantity > 0:
            threshold = position.average_price * (Decimal(1) - rate)
            triggered = event.price <= threshold
            side = Side.SELL
        else:
            threshold = position.average_price * (Decimal(1) + rate)
            triggered = event.price >= threshold
            side = Side.BUY
        if not triggered:
            return
        intent = OrderIntent(
            client_order_id=f"LIQ-{event.symbol}-{state.liquidation_count + 1}",
            symbol=event.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=abs(position.quantity),
            submitted_at=event.timestamp,
            reduce_only=True,
        )
        self._execute(
            intent,
            abs(position.quantity),
            _round_adverse(event.price, instrument.tick_size, side),
            LiquidityRole.LIQUIDATION,
            request.assumptions.liquidation_fee_rate,
            event.timestamp,
            state,
        )
        state.liquidation_count += 1
        self._ledger(
            state,
            event.timestamp,
            LedgerEventType.LIQUIDATED,
            event.symbol,
            intent.client_order_id,
            (("model", LiquidationModel.APPROXIMATE.value), ("threshold", str(threshold))),
        )
        for order in orders:
            if not order.closed and order.intent.symbol == event.symbol:
                self._cancel(order, event.timestamp, state, "LIQUIDATION")

    @staticmethod
    def _record_equity(timestamp: datetime, state: _State, *, append: bool = True) -> EquityPoint:
        cash, unrealized, equity = ReferenceBarBacktestEngine._equity_components(state)
        point = EquityPoint(timestamp, cash, unrealized, equity)
        if append:
            state.equity_curve.append(point)
        return point

    @staticmethod
    def _equity(state: _State) -> Decimal:
        return ReferenceBarBacktestEngine._equity_components(state)[2]

    @staticmethod
    def _equity_components(state: _State) -> tuple[Decimal, Decimal, Decimal]:
        unrealized = Decimal(0)
        for symbol, position in state.positions.items():
            if position.quantity and position.average_price is not None:
                mark = state.last_prices.get(symbol, position.average_price)
                unrealized += position.quantity * (mark - position.average_price)
        return state.cash, unrealized, state.cash + unrealized

    def _cancel(
        self, order: _WorkingOrder, timestamp: datetime, state: _State, reason: str
    ) -> None:
        order.closed = True
        self._ledger(
            state,
            timestamp,
            LedgerEventType.ORDER_CANCELED,
            order.intent.symbol,
            order.intent.client_order_id,
            (("reason", reason),),
        )

    @staticmethod
    def _ledger(
        state: _State,
        timestamp: datetime,
        event_type: LedgerEventType,
        symbol: str,
        client_order_id: str | None,
        details: tuple[tuple[str, str], ...] = (),
    ) -> None:
        state.ordinal += 1
        state.pending_ledger.append(
            (timestamp.astimezone(UTC), state.ordinal, event_type, symbol, client_order_id, details)
        )

    @staticmethod
    def _finalize_ledger(state: _State) -> tuple[LedgerEvent, ...]:
        ordered = sorted(state.pending_ledger, key=lambda item: (item[0], item[1]))
        return tuple(
            LedgerEvent(sequence, timestamp, event_type, symbol, client_order_id, details)
            for sequence, (
                timestamp,
                _ordinal,
                event_type,
                symbol,
                client_order_id,
                details,
            ) in enumerate(ordered, start=1)
        )


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def _round_adverse(value: Decimal, tick: Decimal, side: Side) -> Decimal:
    rounding = ROUND_CEILING if side is Side.BUY else ROUND_FLOOR
    return (value / tick).to_integral_value(rounding=rounding) * tick


def _run_id(request: BacktestRequest) -> str:
    digest = hashlib.sha256(f"{ENGINE_VERSION}|{request!r}".encode()).hexdigest()
    return f"BT-{digest[:20].upper()}"


def _order_sort_key(intent: OrderIntent) -> tuple[datetime, str]:
    timestamp = intent.submitted_at
    normalized = (
        timestamp.replace(tzinfo=UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None
        else timestamp.astimezone(UTC)
    )
    return normalized, intent.client_order_id
