"""Tests for the non-trading command-line surface."""

import json

import pytest

from ai_trading_lab import cli
from ai_trading_lab.settings import LiveModeBlockedError, Settings


def test_status_payload_is_safe() -> None:
    payload = cli.status_payload(Settings())
    assert payload["phase"] == 1
    assert payload["status"] == "healthy"
    assert payload["live_trading"] == "BLOCKED"


def test_status_command_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "RESEARCH"
    assert payload["service"] == "ai-trading-lab"


def test_live_environment_blocks_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATL_MODE", "LIVE")
    with pytest.raises(LiveModeBlockedError):
        cli.main(["status"])


def test_service_starts_and_stops(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    callbacks: dict[int, object] = {}

    def capture_signal(signum: int, callback: object) -> None:
        callbacks[signum] = callback

    def stop_immediately(self: object, timeout: float | None = None) -> bool:
        del timeout
        return True

    monkeypatch.setattr(cli.signal, "signal", capture_signal)
    monkeypatch.setattr(cli.threading.Event, "wait", stop_immediately)
    assert cli.run_service(Settings()) == 0
    events = [json.loads(line)["event"] for line in capsys.readouterr().out.splitlines()]
    assert events == ["service_started", "service_stopped"]
    assert cli.signal.SIGTERM in callbacks
    assert cli.signal.SIGINT in callbacks
    term_callback = callbacks[cli.signal.SIGTERM]
    assert callable(term_callback)
    term_callback(cli.signal.SIGTERM, None)


def test_service_command_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "run_service", lambda _settings: 17)
    assert cli.main(["service"]) == 17


def test_unhandled_command_is_defensive(monkeypatch: pytest.MonkeyPatch) -> None:
    class Args:
        command = "unexpected"

    class Parser:
        def parse_args(self: object, _argv: object) -> Args:
            return Args()

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())
    with pytest.raises(AssertionError, match="Unhandled command"):
        cli.main([])
