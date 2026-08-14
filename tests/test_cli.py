"""Tests for the non-trading command-line surface."""

import json
from pathlib import Path

import pytest

from ai_trading_lab import cli
from ai_trading_lab.settings import LiveModeBlockedError, Settings


def test_status_payload_is_safe() -> None:
    payload = cli.status_payload(Settings())
    assert payload["phase"] == 5
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


def test_backtest_self_test_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["backtest", "self-test"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert cli.main(["backtest", "self-test"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first == second
    assert first["status"] == "PASS"
    assert first["live_trading"] == "BLOCKED"


def test_experiment_self_test_writes_only_to_requested_root(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert cli.main(["experiment", "self-test", "--root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["experiment_id"] == "EXP-000001"
    assert payload["status"] == "COMPLETE"
    assert payload["verdict"] == "INCONCLUSIVE"
    assert payload["live_trading"] == "BLOCKED"
    assert (tmp_path / "experiments" / "EXP-000001" / "manifest.json").is_file()


def test_benchmark_self_test_records_distribution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli,
        "benchmark_smoke_payload",
        lambda root: {
            "status": "PASS",
            "root": str(root),
            "experiments_recorded": 103,
            "live_trading": "BLOCKED",
        },
    )
    assert cli.main(["benchmark", "self-test", "--root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["experiments_recorded"] == 103
    assert payload["root"] == str(tmp_path)


def test_unhandled_command_is_defensive(monkeypatch: pytest.MonkeyPatch) -> None:
    class Args:
        command = "unexpected"

    class Parser:
        def parse_args(self: object, _argv: object) -> Args:
            return Args()

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())
    with pytest.raises(AssertionError, match="Unhandled command"):
        cli.main([])


def test_cli_timestamp_and_symbol_validation() -> None:
    assert cli._utc_timestamp("2026-01-01T00:00:00Z").isoformat().endswith("+00:00")
    assert cli._symbols(" btcusdt,ETHUSDT,btcusdt ") == ("BTCUSDT", "ETHUSDT")
    with pytest.raises(ValueError, match="explicit UTC"):
        cli._utc_timestamp("2026-01-01T00:00:00")
    with pytest.raises(ValueError, match="expressed in UTC"):
        cli._utc_timestamp("2026-01-01T01:00:00+01:00")
    with pytest.raises(ValueError, match="symbols"):
        cli._symbols("bad symbol")


def test_data_commands_dispatch_without_real_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    class Result:
        dataset_version = "DS-TEST"
        status = "CURATED"
        row_count = 2
        validation_errors = 0
        validation_warnings = 0
        manifest_path = tmp_path / "manifest.json"

    class Service:
        def __init__(self, *_args: object) -> None:
            pass

        def ingest_instruments(self, symbols: frozenset[str]) -> Result:
            assert symbols == frozenset({"BTCUSDT"})
            return Result()

        def ingest_candles(self, *args: object, **kwargs: object) -> Result:
            assert args[:2] == ("BTCUSDT", cli.Timeframe.ONE_MINUTE)
            assert kwargs["start"].tzinfo is not None
            return Result()

    monkeypatch.setattr(cli, "DataIngestionService", Service)
    assert cli.main(["data", "instruments", "--symbols", "BTCUSDT"]) == 0
    assert json.loads(capsys.readouterr().out)["dataset_version"] == "DS-TEST"
    assert (
        cli.main(
            [
                "data",
                "candles",
                "--symbol",
                "BTCUSDT",
                "--timeframe",
                "1m",
                "--start",
                "2026-01-01T00:00:00Z",
                "--end",
                "2026-01-01T00:02:00Z",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["live_trading"] == "BLOCKED"


def test_data_transport_failure_is_structured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingService:
        def __init__(self, *_args: object) -> None:
            pass

        def ingest_instruments(self, _symbols: frozenset[str]) -> object:
            raise cli.BybitAPIError("public endpoint unavailable")

    monkeypatch.setattr(cli, "DataIngestionService", FailingService)
    assert cli.main(["data", "instruments", "--symbols", "BTCUSDT"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload == {
        "error": "BybitAPIError",
        "live_trading": "BLOCKED",
        "message": "public endpoint unavailable",
        "status": "FAILED",
    }
