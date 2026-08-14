"""Safe command-line surface for infrastructure and public data ingestion."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from collections.abc import Sequence
from datetime import UTC, datetime

from ai_trading_lab.backtesting.scenarios import reference_smoke_payload
from ai_trading_lab.data.adapters.bybit_v5 import BybitAPIError, BybitV5PublicClient
from ai_trading_lab.data.contracts import INITIAL_SYMBOLS, Timeframe
from ai_trading_lab.data.pipeline import DataIngestionService, IngestionResult
from ai_trading_lab.data.storage import DataLake
from ai_trading_lab.settings import Settings


def build_parser() -> argparse.ArgumentParser:
    """Build the small, non-trading PHASE 1 command surface."""
    parser = argparse.ArgumentParser(prog="atl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="print a safe configuration status")
    status.add_argument("--healthcheck", action="store_true", help=argparse.SUPPRESS)
    subparsers.add_parser("service", help="run the network-disabled infrastructure heartbeat")
    data = subparsers.add_parser("data", help="ingest credential-free public market data")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    instruments = data_commands.add_parser("instruments", help="snapshot Bybit instruments")
    instruments.add_argument(
        "--symbols",
        default=",".join(sorted(INITIAL_SYMBOLS)),
        help="comma-separated symbols; defaults to the initial research universe",
    )
    candles = data_commands.add_parser("candles", help="ingest closed Bybit candles")
    candles.add_argument("--symbol", required=True)
    candles.add_argument("--timeframe", required=True, choices=[item.value for item in Timeframe])
    candles.add_argument("--start", required=True, help="inclusive ISO-8601 UTC timestamp")
    candles.add_argument("--end", required=True, help="exclusive ISO-8601 UTC timestamp")
    backtest = subparsers.add_parser("backtest", help="run safe backtesting utilities")
    backtest_commands = backtest.add_subparsers(dest="backtest_command", required=True)
    backtest_commands.add_parser("self-test", help="run the deterministic synthetic kernel check")
    return parser


def status_payload(settings: Settings) -> dict[str, object]:
    """Build the public health/status payload."""
    return {
        "service": "ai-trading-lab",
        "phase": 3,
        "status": "healthy",
        **settings.public_status(),
    }


def _print_payload(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def run_service(settings: Settings) -> int:
    """Run a stoppable heartbeat; this process performs no trading or network access."""
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    _print_payload({**status_payload(settings), "event": "service_started"})
    stop_event.wait()
    _print_payload({**status_payload(settings), "event": "service_stopped"})
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the safe pre-live CLI."""
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "status":
        _print_payload(status_payload(settings))
        return 0
    if args.command == "service":
        return run_service(settings)
    if args.command == "backtest":
        if args.backtest_command == "self-test":
            _print_payload(reference_smoke_payload())
            return 0
        raise AssertionError(f"Unhandled backtest command: {args.backtest_command}")
    if args.command == "data":
        lake = DataLake(settings.data_root)
        service = DataIngestionService(BybitV5PublicClient(raw_page_sink=lake.write_raw_page), lake)
        try:
            if args.data_command == "instruments":
                symbols = frozenset(_symbols(args.symbols))
                _print_payload(_result_payload(service.ingest_instruments(symbols)))
                return 0
            if args.data_command == "candles":
                result = service.ingest_candles(
                    args.symbol,
                    Timeframe(args.timeframe),
                    start=_utc_timestamp(args.start),
                    end=_utc_timestamp(args.end),
                )
                _print_payload(_result_payload(result))
                return 0
        except BybitAPIError as exc:
            print(
                json.dumps(
                    {
                        "status": "FAILED",
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "live_trading": "BLOCKED",
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
            return 2
        raise AssertionError(f"Unhandled data command: {args.data_command}")
    raise AssertionError(f"Unhandled command: {args.command}")


def _utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None:
        raise ValueError("timestamps must include an explicit UTC offset")
    if offset.total_seconds() != 0:
        raise ValueError("timestamps must be expressed in UTC")
    return parsed.astimezone(UTC)


def _symbols(value: str) -> tuple[str, ...]:
    symbols = tuple(
        dict.fromkeys(item.strip().upper() for item in value.split(",") if item.strip())
    )
    if not symbols or any(not symbol.isalnum() for symbol in symbols):
        raise ValueError("symbols must be a non-empty comma-separated alphanumeric list")
    return symbols


def _result_payload(result: IngestionResult) -> dict[str, object]:
    return {
        "dataset_version": result.dataset_version,
        "status": result.status,
        "rows": result.row_count,
        "validation_errors": result.validation_errors,
        "validation_warnings": result.validation_warnings,
        "manifest": str(result.manifest_path),
        "live_trading": "BLOCKED",
    }
