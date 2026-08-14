"""Safe command-line surface for PHASE 1 infrastructure checks."""

from __future__ import annotations

import argparse
import json
import signal
import threading
from collections.abc import Sequence

from ai_trading_lab.settings import Settings


def build_parser() -> argparse.ArgumentParser:
    """Build the small, non-trading PHASE 1 command surface."""
    parser = argparse.ArgumentParser(prog="atl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="print a safe configuration status")
    status.add_argument("--healthcheck", action="store_true", help=argparse.SUPPRESS)
    subparsers.add_parser("service", help="run the network-disabled infrastructure heartbeat")
    return parser


def status_payload(settings: Settings) -> dict[str, object]:
    """Build the public health/status payload."""
    return {
        "service": "ai-trading-lab",
        "phase": 1,
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
    """Execute the safe PHASE 1 CLI."""
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "status":
        _print_payload(status_payload(settings))
        return 0
    if args.command == "service":
        return run_service(settings)
    raise AssertionError(f"Unhandled command: {args.command}")
