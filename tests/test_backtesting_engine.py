"""Deterministic and conservative execution tests for the T1 reference kernel."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ai_trading_lab.backtesting.contracts import (
    BacktestRequest,
    ExecutionAssumptions,
    FundingEvent,
    LedgerEventType,
    LimitFillPolicy,
    LiquidationModel,
    LiquidityRole,
    MarkPriceEvent,
    OrderIntent,
    OrderType,
    Side,
    TimeInForce,
)
from ai_trading_lab.backtesting.engine import (
    BacktestConfigurationError,
    ReferenceBarBacktestEngine,
)
from ai_trading_lab.data.contracts import Candle, Instrument

START = datetime(2026, 1, 1, tzinfo=UTC)


def _order(
    identifier: str,
    side: Side,
    submitted_at: datetime,
    *,
    quantity: str = "1",
    order_type: OrderType = OrderType.MARKET,
    symbol: str = "BTCUSDT",
    **changes: object,
) -> OrderIntent:
    return OrderIntent(
        client_order_id=identifier,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=Decimal(quantity),
        submitted_at=submitted_at,
        **changes,  # type: ignore[arg-type]
    )


def _request(
    candles: tuple[Candle, ...],
    instrument: Instrument,
    orders: tuple[OrderIntent, ...],
    *,
    assumptions: ExecutionAssumptions | None = None,
    initial_cash: str = "10000",
    funding: tuple[FundingEvent, ...] = (),
    marks: tuple[MarkPriceEvent, ...] = (),
    instruments: tuple[Instrument, ...] | None = None,
) -> BacktestRequest:
    return BacktestRequest(
        dataset_version="DS-TEST-V1",
        candles=candles,
        instruments=instruments or (instrument,),
        orders=orders,
        initial_cash=Decimal(initial_cash),
        assumptions=assumptions or ExecutionAssumptions(),
        funding=funding,
        marks=marks,
    )


def test_market_signal_cannot_fill_on_same_close(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (
        candle_factory(0),
        candle_factory(
            1,
            open=Decimal("110"),
            high=Decimal("112"),
            low=Decimal("109"),
            close=Decimal("111"),
            volume=Decimal("100"),
        ),
    )
    intent = _order("ENTRY", Side.BUY, candles[0].close_time)
    result = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), (intent,)))

    assert result.fills[0].timestamp == candles[1].open_time
    assert result.fills[0].price == Decimal("110.1")
    assert result.fills[0].price != candles[0].close
    assert result.total_fees == Decimal("0.060555")


def test_future_data_does_not_change_prefix(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    prefix = tuple(candle_factory(index) for index in range(3))
    extended = (*prefix, candle_factory(3, close=Decimal("999"), high=Decimal("999")))
    intent = _order("ENTRY", Side.BUY, prefix[0].close_time)
    engine = ReferenceBarBacktestEngine()

    short = engine.run(_request(prefix, instrument_factory(), (intent,)))
    long = engine.run(_request(extended, instrument_factory(), (intent,)))

    assert long.fills == short.fills
    assert long.ledger == short.ledger
    assert long.equity_curve[: len(short.equity_curve)] == short.equity_curve


def test_repeated_run_is_byte_level_domain_deterministic(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index) for index in range(2))
    request = _request(
        candles,
        instrument_factory(),
        (_order("ENTRY", Side.BUY, candles[0].close_time),),
    )
    engine = ReferenceBarBacktestEngine()
    assert engine.run(request) == engine.run(request)
    assert engine.run(request).run_id.startswith("BT-")


def test_limit_requires_cross_by_default_and_touch_is_explicit(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    candles = (
        candle_factory(0),
        candle_factory(1, open=Decimal("100"), low=Decimal("99")),
    )
    intent = _order(
        "LIMIT",
        Side.BUY,
        candles[0].close_time,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("99"),
    )
    strict = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), (intent,)))
    touch = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (intent,),
            assumptions=ExecutionAssumptions(limit_fill_policy=LimitFillPolicy.TOUCH),
        )
    )
    assert not strict.fills
    assert touch.fills[0].price == Decimal("99")
    assert touch.fills[0].liquidity is LiquidityRole.MAKER


def test_market_partial_fill_cancels_remainder(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (candle_factory(0), candle_factory(1, volume=Decimal("10")))
    assumptions = ExecutionAssumptions(max_bar_participation=Decimal("0.05"))
    result = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (_order("LARGE", Side.BUY, candles[0].close_time, quantity="1"),),
            assumptions=assumptions,
        )
    )
    assert result.fills[0].quantity == Decimal("0.5")
    assert any(
        event.event_type is LedgerEventType.ORDER_CANCELED
        and ("reason", "UNFILLED_MARKET_REMAINDER") in event.details
        for event in result.ledger
    )


def test_gtc_limit_can_fill_across_multiple_bars(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (
        candle_factory(0),
        candle_factory(1, low=Decimal("98"), volume=Decimal("5")),
        candle_factory(2, low=Decimal("98"), volume=Decimal("5")),
    )
    intent = _order(
        "LIMIT",
        Side.BUY,
        candles[0].close_time,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("99"),
    )
    assumptions = ExecutionAssumptions(max_bar_participation=Decimal("0.1"))
    result = ReferenceBarBacktestEngine().run(
        _request(candles, instrument_factory(), (intent,), assumptions=assumptions)
    )
    assert [fill.quantity for fill in result.fills] == [Decimal("0.5"), Decimal("0.5")]
    assert all(fill.liquidity is LiquidityRole.MAKER for fill in result.fills)


def test_ioc_and_latency_are_enforced(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index, low=Decimal("99")) for index in range(3))
    ioc = _order(
        "IOC",
        Side.BUY,
        candles[0].close_time,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("98"),
        time_in_force=TimeInForce.IOC,
    )
    delayed = _order("DELAYED", Side.BUY, candles[0].close_time)
    result = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (ioc, delayed),
            assumptions=ExecutionAssumptions(latency_milliseconds=1),
        )
    )
    assert [fill.client_order_id for fill in result.fills] == ["DELAYED"]
    assert result.fills[0].timestamp == candles[2].open_time


def test_same_bar_oco_uses_worst_case_for_long(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (
        candle_factory(0),
        candle_factory(1, open=Decimal("100"), high=Decimal("101"), low=Decimal("99")),
        candle_factory(2, open=Decimal("100"), high=Decimal("106"), low=Decimal("94")),
    )
    entry = _order("ENTRY", Side.BUY, candles[0].close_time)
    stop = _order(
        "STOP",
        Side.SELL,
        candles[1].close_time,
        order_type=OrderType.STOP_MARKET,
        trigger_price=Decimal("95"),
        reduce_only=True,
        oco_group="EXIT",
    )
    target = _order(
        "TARGET",
        Side.SELL,
        candles[1].close_time,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("105"),
        reduce_only=True,
        oco_group="EXIT",
    )
    result = ReferenceBarBacktestEngine().run(
        _request(candles, instrument_factory(), (entry, stop, target))
    )
    assert [fill.client_order_id for fill in result.fills] == ["ENTRY", "STOP"]
    assert result.positions[0].quantity == 0
    assert any(
        event.client_order_id == "TARGET" and ("reason", "OCO_SIBLING_FILLED") in event.details
        for event in result.ledger
    )


@pytest.mark.parametrize(
    ("side", "expected_sign"), [(Side.BUY, Decimal("-1")), (Side.SELL, Decimal("1"))]
)
def test_positive_funding_debits_longs_and_credits_shorts(
    side: Side, expected_sign: Decimal, candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index, open=Decimal("100")) for index in range(3))
    event = FundingEvent("BTCUSDT", candles[2].open_time, Decimal("0.001"), Decimal("100"))
    result = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (_order("ENTRY", side, candles[0].close_time),),
            assumptions=ExecutionAssumptions(max_bar_participation=Decimal(1)),
            funding=(event,),
        )
    )
    assert result.total_funding * expected_sign > 0
    assert abs(result.total_funding) == Decimal("0.100")


def test_reduce_only_caps_quantity_and_cannot_reverse(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index) for index in range(3))
    entry = _order("ENTRY", Side.BUY, candles[0].close_time, quantity="0.5")
    exit_order = _order("EXIT", Side.SELL, candles[1].close_time, quantity="1", reduce_only=True)
    result = ReferenceBarBacktestEngine().run(
        _request(candles, instrument_factory(), (entry, exit_order))
    )
    assert [fill.quantity for fill in result.fills] == [Decimal("0.5"), Decimal("0.5")]
    assert result.positions[0].quantity == 0


def test_invalid_orders_are_audited_not_executed(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index) for index in range(2))
    orders = (
        _order("BAD-QTY", Side.BUY, candles[0].close_time, quantity="0.0005"),
        _order(
            "BAD-PRICE",
            Side.BUY,
            candles[0].close_time,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("99.99"),
        ),
    )
    result = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), orders))
    assert not result.fills
    assert [event.event_type for event in result.ledger] == [
        LedgerEventType.ORDER_REJECTED,
        LedgerEventType.ORDER_REJECTED,
    ]


def test_insufficient_margin_rejects_exposure(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index) for index in range(2))
    result = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (_order("TOO-LARGE", Side.BUY, candles[0].close_time, quantity="2"),),
            initial_cash="40",
        )
    )
    assert not result.fills
    assert ("reason", "INSUFFICIENT_MARGIN") in result.ledger[-1].details


def test_approximate_liquidation_is_flagged_and_closes_position(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index, open=Decimal("100")) for index in range(3))
    mark = MarkPriceEvent("BTCUSDT", candles[2].open_time, Decimal("50"))
    assumptions = ExecutionAssumptions(
        leverage=Decimal("5"), liquidation_model=LiquidationModel.APPROXIMATE
    )
    result = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (_order("ENTRY", Side.BUY, candles[0].close_time),),
            assumptions=assumptions,
            marks=(mark,),
        )
    )
    assert result.liquidation_count == 1
    assert result.positions[0].quantity == 0
    assert not result.paper_eligible
    assert result.fills[-1].liquidity is LiquidityRole.LIQUIDATION


def test_multi_symbol_event_order_is_stable(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    btc = tuple(candle_factory(index) for index in range(2))
    eth = tuple(
        candle_factory(
            index,
            symbol="ETHUSDT",
            open=Decimal("50"),
            high=Decimal("51"),
            low=Decimal("49"),
            close=Decimal("50.5"),
            turnover=Decimal("500"),
        )
        for index in range(2)
    )
    instruments = (instrument_factory(), instrument_factory("ETHUSDT"))
    orders = (
        _order("ETH", Side.BUY, eth[0].close_time, symbol="ETHUSDT"),
        _order("BTC", Side.BUY, btc[0].close_time),
    )
    request = _request(btc + eth, instruments[0], orders, instruments=instruments)
    result = ReferenceBarBacktestEngine().run(request)
    assert [fill.client_order_id for fill in result.fills] == ["BTC", "ETH"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda request: replace(request, dataset_version=" "), "dataset_version"),
        (lambda request: replace(request, initial_cash=Decimal(0)), "initial_cash"),
        (lambda request: replace(request, candles=()), "candles"),
        (
            lambda request: replace(request, instruments=(request.instruments[0],) * 2),
            "unique",
        ),
    ],
)
def test_invalid_backtest_request_fails_closed(
    mutator, message: str, candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    request = _request((candle_factory(0),), instrument_factory(), ())
    with pytest.raises(BacktestConfigurationError, match=message):
        ReferenceBarBacktestEngine().run(mutator(request))


def test_external_events_must_align_to_a_bar(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candle = candle_factory(0)
    mark = MarkPriceEvent("BTCUSDT", START + timedelta(seconds=30), Decimal("100"))
    with pytest.raises(BacktestConfigurationError, match="align"):
        ReferenceBarBacktestEngine().run(
            _request((candle,), instrument_factory(), (), marks=(mark,))
        )


def test_position_can_flip_and_tracks_new_average(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index, volume=Decimal("100")) for index in range(3))
    orders = (
        _order("LONG", Side.BUY, candles[0].close_time, quantity="0.5"),
        _order("FLIP", Side.SELL, candles[1].close_time, quantity="1"),
    )
    result = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), orders))
    assert result.positions[0].quantity == Decimal("-0.5")
    assert result.positions[0].average_price == result.fills[-1].price


@pytest.mark.parametrize(
    ("side", "trigger", "bar", "expected"),
    [
        (Side.BUY, "101", {"open": Decimal("102"), "high": Decimal("103")}, "102.1"),
        (Side.BUY, "101", {"open": Decimal("100"), "high": Decimal("102")}, "101.1"),
        (Side.SELL, "99", {"open": Decimal("98"), "low": Decimal("97")}, "97.9"),
        (Side.SELL, "99", {"open": Decimal("100"), "low": Decimal("98")}, "98.9"),
    ],
)
def test_stop_market_gap_and_intrabar_trigger_are_adverse(
    side: Side,
    trigger: str,
    bar: dict[str, Decimal],
    expected: str,
    candle_factory,
    instrument_factory,
) -> None:  # type: ignore[no-untyped-def]
    normalized = {"high": Decimal("103"), "low": Decimal("97"), "close": Decimal("100"), **bar}
    candles = (candle_factory(0), candle_factory(1, **normalized))
    intent = _order(
        "STOP",
        side,
        candles[0].close_time,
        order_type=OrderType.STOP_MARKET,
        trigger_price=Decimal(trigger),
    )
    result = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), (intent,)))
    assert result.fills[0].price == Decimal(expected)


@pytest.mark.parametrize(
    ("side", "limit", "bar"),
    [
        (Side.BUY, "101", {"open": Decimal("100")}),
        (Side.SELL, "99", {"open": Decimal("100")}),
        (Side.SELL, "101", {"open": Decimal("100"), "high": Decimal("102")}),
    ],
)
def test_marketable_and_crossed_limits_have_explicit_liquidity(
    side: Side,
    limit: str,
    bar: dict[str, Decimal],
    candle_factory,
    instrument_factory,
) -> None:  # type: ignore[no-untyped-def]
    candles = (candle_factory(0), candle_factory(1, **bar))
    intent = _order(
        "LIMIT",
        side,
        candles[0].close_time,
        order_type=OrderType.LIMIT,
        limit_price=Decimal(limit),
    )
    result = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), (intent,)))
    expected = LiquidityRole.MAKER if side is Side.SELL and limit == "101" else LiquidityRole.TAKER
    assert result.fills[0].liquidity is expected


def test_reduce_only_and_min_notional_fail_closed(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index) for index in range(2))
    reduce_only = _order("REDUCE", Side.SELL, candles[0].close_time, reduce_only=True)
    too_small = _order("NOTIONAL", Side.BUY, candles[0].close_time, quantity="0.5")
    instrument = instrument_factory(min_notional=Decimal("75"))
    result = ReferenceBarBacktestEngine().run(
        _request(candles, instrument, (reduce_only, too_small))
    )
    reasons = {detail for event in result.ledger for detail in event.details}
    assert ("reason", "REDUCE_ONLY_WOULD_INCREASE") in reasons
    assert ("reason", "BELOW_MINIMUM_NOTIONAL") in reasons


def test_ioc_partial_fill_cancels_remainder(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = (candle_factory(0), candle_factory(1, low=Decimal("98")))
    intent = _order(
        "IOC-PARTIAL",
        Side.BUY,
        candles[0].close_time,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("99"),
        time_in_force=TimeInForce.IOC,
    )
    result = ReferenceBarBacktestEngine().run(_request(candles, instrument_factory(), (intent,)))
    assert result.fills[0].quantity == Decimal("0.5")
    assert ("reason", "IOC_REMAINDER") in result.ledger[-1].details


def test_short_liquidation_and_non_triggering_marks(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candles = tuple(candle_factory(index, volume=Decimal("100")) for index in range(4))
    marks = (
        MarkPriceEvent("BTCUSDT", candles[0].open_time, Decimal("100")),
        MarkPriceEvent("BTCUSDT", candles[2].open_time, Decimal("110")),
        MarkPriceEvent("BTCUSDT", candles[3].open_time, Decimal("150")),
    )
    assumptions = ExecutionAssumptions(
        leverage=Decimal("5"), liquidation_model=LiquidationModel.APPROXIMATE
    )
    result = ReferenceBarBacktestEngine().run(
        _request(
            candles,
            instrument_factory(),
            (_order("SHORT", Side.SELL, candles[0].close_time),),
            assumptions=assumptions,
            marks=marks,
        )
    )
    assert result.liquidation_count == 1
    assert result.fills[-1].side is Side.BUY


def test_invalid_mark_price_fails_closed(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candle = candle_factory(0)
    mark = MarkPriceEvent("BTCUSDT", candle.open_time, Decimal(0))
    with pytest.raises(BacktestConfigurationError, match="positive"):
        ReferenceBarBacktestEngine().run(
            _request((candle,), instrument_factory(), (), marks=(mark,))
        )


def test_request_rejects_excess_leverage_missing_instrument_and_bad_data(
    candle_factory, instrument_factory
) -> None:  # type: ignore[no-untyped-def]
    candle = candle_factory(0)
    engine = ReferenceBarBacktestEngine()
    with pytest.raises(BacktestConfigurationError, match="maximum"):
        engine.run(
            _request(
                (candle,),
                instrument_factory(max_leverage=Decimal("2")),
                (),
                assumptions=ExecutionAssumptions(leverage=Decimal("3")),
            )
        )
    with pytest.raises(BacktestConfigurationError, match="missing instrument"):
        engine.run(_request((replace(candle, symbol="ETHUSDT"),), instrument_factory(), ()))
    with pytest.raises(BacktestConfigurationError, match="invalid candle"):
        engine.run(_request((replace(candle, high=Decimal("1")),), instrument_factory(), ()))


def test_order_rejection_reasons_are_complete(candle_factory, instrument_factory) -> None:  # type: ignore[no-untyped-def]
    candle = candle_factory(0)
    now = candle.open_time
    valid = _order("DUP", Side.BUY, now)
    orders = (
        valid,
        valid,
        _order("UNKNOWN", Side.BUY, now, symbol="ETHUSDT"),
        replace(_order("NAIVE", Side.BUY, now), submitted_at=datetime(2026, 1, 1)),
        _order("SMALL", Side.BUY, now, quantity="0.001"),
        _order("LARGE", Side.BUY, now, quantity="1001"),
        replace(_order("EXTRA-LIMIT", Side.BUY, now), limit_price=Decimal("99")),
        replace(_order("EXTRA-TRIGGER", Side.BUY, now), trigger_price=Decimal("99")),
        _order("BAD-STOP", Side.BUY, now, order_type=OrderType.STOP_MARKET),
    )
    instrument = instrument_factory(min_order_quantity=Decimal("0.01"))
    result = ReferenceBarBacktestEngine().run(_request((candle,), instrument, orders))
    reasons = {value for event in result.ledger for key, value in event.details if key == "reason"}
    assert {
        "INVALID_OR_DUPLICATE_CLIENT_ORDER_ID",
        "UNKNOWN_INSTRUMENT",
        "NAIVE_SUBMISSION_TIME",
        "BELOW_MINIMUM_QUANTITY",
        "ABOVE_MAXIMUM_QUANTITY",
        "UNEXPECTED_LIMIT_PRICE",
        "UNEXPECTED_TRIGGER_PRICE",
        "INVALID_TRIGGER_PRICE",
    } <= reasons
