"""Safety and configuration tests."""

from pathlib import Path

import pytest

from ai_trading_lab.settings import LiveModeBlockedError, RunMode, Settings


@pytest.mark.parametrize("value", ["RESEARCH", "research", " RESEARCH "])
def test_research_mode_parses_case_insensitively(value: str) -> None:
    assert RunMode.parse(value) is RunMode.RESEARCH


@pytest.mark.parametrize("value", ["BACKTEST", "backtest", " PAPER "])
def test_non_live_modes_are_available(value: str) -> None:
    assert RunMode.parse(value).value == value.strip().upper()


@pytest.mark.parametrize("value", ["LIVE", "live", " Live "])
def test_live_mode_is_always_blocked(value: str) -> None:
    with pytest.raises(LiveModeBlockedError, match="hard-blocked"):
        RunMode.parse(value)


def test_unknown_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported ATL_MODE"):
        RunMode.parse("production")


def test_settings_default_to_research() -> None:
    assert Settings.from_env({}) == Settings(mode=RunMode.RESEARCH, log_level="INFO")


def test_settings_read_safe_environment() -> None:
    settings = Settings.from_env(
        {"ATL_MODE": "paper", "ATL_LOG_LEVEL": "warning", "ATL_DATA_ROOT": "/market-data"}
    )
    assert settings.mode is RunMode.PAPER
    assert settings.log_level == "WARNING"
    assert settings.data_root == Path("/market-data")


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported log level"):
        Settings(log_level="verbose")
    with pytest.raises(ValueError, match="data_root"):
        Settings(data_root=Path(""))


def test_public_status_contains_no_credentials() -> None:
    status = Settings().public_status()
    assert status == {
        "mode": "RESEARCH",
        "log_level": "INFO",
        "allowed_modes": ["RESEARCH", "BACKTEST", "PAPER"],
        "live_trading": "BLOCKED",
        "data_root": "data",
    }
    assert "LIVE" not in status["allowed_modes"]
