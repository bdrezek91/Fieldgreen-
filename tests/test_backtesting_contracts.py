"""Boundary validation for immutable backtesting contracts."""

from decimal import Decimal

import pytest

from ai_trading_lab.backtesting.contracts import ExecutionAssumptions, Side


def test_side_sign_is_exact_decimal() -> None:
    assert Side.BUY.sign == Decimal(1)
    assert Side.SELL.sign == Decimal(-1)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"maker_fee_rate": Decimal("-0.1")}, "rates"),
        ({"max_bar_participation": Decimal(0)}, "participation"),
        ({"max_bar_participation": Decimal("1.1")}, "participation"),
        ({"leverage": Decimal("0.5")}, "leverage"),
        ({"latency_milliseconds": -1}, "latency"),
        ({"version": " "}, "version"),
    ],
)
def test_invalid_execution_assumptions_fail_closed(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ExecutionAssumptions(**changes)  # type: ignore[arg-type]
