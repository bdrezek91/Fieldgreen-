"""SQLite identity registry with immutable JSON, Parquet and Markdown evidence."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Final

import pyarrow as pa
import pyarrow.parquet as pq

from ai_trading_lab.analytics.contracts import AnalyticsResult, PerformanceMetrics, TradeRecord
from ai_trading_lab.analytics.metrics import BacktestAnalytics
from ai_trading_lab.backtesting.artifacts import BacktestArtifactStore
from ai_trading_lab.backtesting.contracts import BacktestRequest, BacktestResult
from ai_trading_lab.experiments.contracts import (
    ExperimentRecord,
    ExperimentSpec,
    ExperimentStatus,
    ResearchVerdict,
)
from ai_trading_lab.serialization import canonical_json_bytes, file_sha256

DECIMAL: Final = pa.decimal128(38, 18)
TIMESTAMP: Final = pa.timestamp("ms", tz="UTC")
COMMIT_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")


class ExperimentValidationError(ValueError):
    """Raised before reserving an ID when evidence is inconsistent."""


class ExperimentStore:
    """Allocate monotonic IDs and persist a recoverable experiment lifecycle."""

    def __init__(self, root: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.root = root.resolve()
        self.experiments_root = self.root / "experiments"
        self.database = self.experiments_root / "registry.sqlite3"
        self.clock = clock or (lambda: datetime.now(UTC))
        self.experiments_root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record(
        self,
        spec: ExperimentSpec,
        request: BacktestRequest,
        result: BacktestResult,
        analytics: AnalyticsResult,
    ) -> ExperimentRecord:
        """Reserve an ID, atomically publish evidence and mark the row complete."""
        self._validate(spec, request, result, analytics)
        created_at = _aware_utc(self.clock())
        backtest_artifact = BacktestArtifactStore(self.root).write(request, result)
        experiment_id = self._reserve(spec, result, created_at)
        target = self.experiments_root / experiment_id
        temporary = Path(tempfile.mkdtemp(prefix=f".{experiment_id}.", dir=self.experiments_root))
        try:
            self._write_bundle(
                temporary,
                experiment_id,
                created_at,
                spec,
                request,
                result,
                analytics,
                backtest_artifact.path,
                backtest_artifact.sha256,
            )
            if target.exists():
                raise FileExistsError(f"experiment artifact already exists: {target}")
            os.replace(temporary, target)
            manifest_hash = file_sha256(target / "manifest.json")
            completed_at = _aware_utc(self.clock())
            self._complete(experiment_id, target, manifest_hash, completed_at)
            return self.get(experiment_id)
        except Exception as exc:
            if temporary.exists():
                shutil.rmtree(temporary)
            self._fail(experiment_id, str(exc))
            raise

    def get(self, experiment_id: str) -> ExperimentRecord:
        """Read one experiment row by canonical ID."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)
            ).fetchone()
        if row is None:
            raise KeyError(experiment_id)
        return _record_from_row(row, self.root)

    def list_records(self) -> tuple[ExperimentRecord, ...]:
        """List records in monotonic allocation order."""
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM experiments ORDER BY id").fetchall()
        return tuple(_record_from_row(row, self.root) for row in rows)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    git_commit TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    backtest_run_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    artifact_path TEXT,
                    artifact_sha256 TEXT,
                    error TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _validate(
        spec: ExperimentSpec,
        request: BacktestRequest,
        result: BacktestResult,
        analytics: AnalyticsResult,
    ) -> None:
        if COMMIT_PATTERN.fullmatch(spec.git_commit) is None:
            raise ExperimentValidationError("git_commit must be a lowercase 40-character SHA")
        if not spec.hypothesis_id.strip() or not spec.strategy_version.strip():
            raise ExperimentValidationError("hypothesis_id and strategy_version are required")
        if not spec.decision_reason.strip():
            raise ExperimentValidationError("decision_reason is required")
        keys = [key for key, _value in spec.parameters]
        if any(not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ExperimentValidationError("parameter keys must be non-empty and unique")
        if request.dataset_version != result.dataset_version:
            raise ExperimentValidationError("request and result dataset versions differ")
        if analytics.backtest_run_id != result.run_id:
            raise ExperimentValidationError("analytics and result run IDs differ")
        if analytics != BacktestAnalytics().analyze(request, result):
            raise ExperimentValidationError("analytics are not the canonical result for this run")

    def _reserve(self, spec: ExperimentSpec, result: BacktestResult, created_at: datetime) -> str:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO experiments (
                    experiment_id, status, created_at, git_commit, dataset_version,
                    backtest_run_id, verdict
                ) VALUES (NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ExperimentStatus.RESERVED.value,
                    created_at.isoformat(),
                    spec.git_commit,
                    result.dataset_version,
                    result.run_id,
                    spec.verdict.value,
                ),
            )
            identifier = cursor.lastrowid
            if identifier is None:
                raise RuntimeError("SQLite did not allocate an experiment ID")
            experiment_id = f"EXP-{identifier:06d}"
            connection.execute(
                "UPDATE experiments SET experiment_id = ? WHERE id = ?",
                (experiment_id, identifier),
            )
            connection.commit()
            return experiment_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _complete(
        self, experiment_id: str, target: Path, digest: str, completed_at: datetime
    ) -> None:
        relative = target.relative_to(self.root).as_posix()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE experiments
                SET status = ?, completed_at = ?, artifact_path = ?, artifact_sha256 = ?
                WHERE experiment_id = ? AND status = ?
                """,
                (
                    ExperimentStatus.COMPLETE.value,
                    completed_at.isoformat(),
                    relative,
                    digest,
                    experiment_id,
                    ExperimentStatus.RESERVED.value,
                ),
            )

    def _fail(self, experiment_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE experiments SET status = ?, error = ? WHERE experiment_id = ?",
                (ExperimentStatus.FAILED.value, error[:2000], experiment_id),
            )

    def _write_bundle(
        self,
        directory: Path,
        experiment_id: str,
        created_at: datetime,
        spec: ExperimentSpec,
        request: BacktestRequest,
        result: BacktestResult,
        analytics: AnalyticsResult,
        backtest_path: Path,
        backtest_sha256: str,
    ) -> None:
        metrics_path = directory / "metrics.json"
        metrics_path.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "performance-metrics-v1",
                    "metric_version": analytics.metric_version,
                    "backtest_run_id": analytics.backtest_run_id,
                    "metrics": analytics.metrics,
                }
            )
        )
        trades_path = directory / "trades.parquet"
        pq.write_table(
            _trade_table(analytics.trades),
            trades_path,
            compression="zstd",
            write_statistics=True,
        )
        report_path = directory / "report.md"
        report_path.write_text(
            _render_report(experiment_id, spec, request, result, analytics), encoding="utf-8"
        )
        manifest = {
            "schema_version": "experiment-manifest-v1",
            "experiment_id": experiment_id,
            "timestamp": created_at,
            "git_commit": spec.git_commit,
            "hypothesis_id": spec.hypothesis_id,
            "strategy_version": spec.strategy_version,
            "parameters": dict(spec.parameters),
            "verdict": spec.verdict,
            "decision_reason": spec.decision_reason,
            "data": {
                "dataset_version": request.dataset_version,
                "date_range": {
                    "start": min(item.open_time for item in request.candles),
                    "end": max(item.close_time for item in request.candles),
                },
                "symbols": sorted({item.symbol for item in request.candles}),
                "timeframes": sorted({item.timeframe.value for item in request.candles}),
                "candle_count": len(request.candles),
            },
            "backtest": {
                "run_id": result.run_id,
                "engine_version": result.engine_version,
                "assumptions_version": result.assumptions_version,
                "execution_assumptions": request.assumptions,
                "funding_events": request.funding,
                "mark_events": request.marks,
                "request_sha256": hashlib.sha256(canonical_json_bytes(request)).hexdigest(),
            },
            "analytics": {
                "metric_version": analytics.metric_version,
                "trade_count": len(analytics.trades),
            },
            "artifacts": {
                "backtest": {
                    "path": backtest_path.relative_to(self.root),
                    "sha256": backtest_sha256,
                },
                "metrics": {"path": "metrics.json", "sha256": file_sha256(metrics_path)},
                "trades": {"path": "trades.parquet", "sha256": file_sha256(trades_path)},
                "report": {"path": "report.md", "sha256": file_sha256(report_path)},
            },
        }
        (directory / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def _trade_table(trades: tuple[TradeRecord, ...]) -> pa.Table:
    schema = pa.schema(
        [
            pa.field("trade_id", pa.string(), nullable=False),
            pa.field("symbol", pa.string(), nullable=False),
            pa.field("direction", pa.string(), nullable=False),
            pa.field("entry_time", TIMESTAMP, nullable=False),
            pa.field("exit_time", TIMESTAMP, nullable=False),
            pa.field("quantity", DECIMAL, nullable=False),
            pa.field("entry_price", DECIMAL, nullable=False),
            pa.field("exit_price", DECIMAL, nullable=False),
            pa.field("gross_pnl", DECIMAL, nullable=False),
            pa.field("entry_fee", DECIMAL, nullable=False),
            pa.field("exit_fee", DECIMAL, nullable=False),
            pa.field("net_pnl", DECIMAL, nullable=False),
            pa.field("return_on_entry_notional", DECIMAL, nullable=False),
            pa.field("initial_risk", DECIMAL),
            pa.field("r_multiple", DECIMAL),
            pa.field("mae", DECIMAL),
            pa.field("mfe", DECIMAL),
        ]
    )
    rows = []
    for trade in trades:
        row: dict[str, object] = {
            field.name: getattr(trade, field.name) for field in fields(TradeRecord)
        }
        row["direction"] = trade.direction.value
        for name in (
            "quantity",
            "entry_price",
            "exit_price",
            "gross_pnl",
            "entry_fee",
            "exit_fee",
            "net_pnl",
            "return_on_entry_notional",
            "initial_risk",
            "r_multiple",
            "mae",
            "mfe",
        ):
            value = row[name]
            row[name] = _scale(value) if isinstance(value, Decimal) else None
        rows.append(row)
    return pa.Table.from_pylist(rows, schema=schema)


def _scale(value: Decimal) -> Decimal:
    try:
        with localcontext() as context:
            context.prec = 38
            return value.quantize(Decimal("0.000000000000000001"))
    except ArithmeticError as exc:
        raise ValueError(f"decimal value cannot fit decimal128(38,18): {value}") from exc


def _render_report(
    experiment_id: str,
    spec: ExperimentSpec,
    request: BacktestRequest,
    result: BacktestResult,
    analytics: AnalyticsResult,
) -> str:
    metrics = analytics.metrics
    lines = [
        f"# Experiment {experiment_id}",
        "",
        f"- Verdict: **{spec.verdict.value}**",
        f"- Decision: {spec.decision_reason}",
        f"- Hypothesis: `{spec.hypothesis_id}`",
        f"- Strategy version: `{spec.strategy_version}`",
        f"- Git commit: `{spec.git_commit}`",
        f"- Dataset: `{request.dataset_version}`",
        f"- Backtest: `{result.run_id}`",
        f"- Metrics: `{analytics.metric_version}`",
        "",
        "## Performance",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for field in fields(PerformanceMetrics):
        value = getattr(metrics, field.name)
        lines.append(f"| {field.name} | {_report_value(value)} |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report records evidence; it does not promote a strategy automatically. Null",
            "metrics are unavailable from the current contracts and must not be imputed.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value) or "—"
    return str(value)


def _record_from_row(row: sqlite3.Row, root: Path) -> ExperimentRecord:
    relative = row["artifact_path"]
    return ExperimentRecord(
        experiment_id=str(row["experiment_id"]),
        status=ExperimentStatus(str(row["status"])),
        created_at=datetime.fromisoformat(str(row["created_at"])).astimezone(UTC),
        completed_at=(
            datetime.fromisoformat(str(row["completed_at"])).astimezone(UTC)
            if row["completed_at"]
            else None
        ),
        git_commit=str(row["git_commit"]),
        dataset_version=str(row["dataset_version"]),
        backtest_run_id=str(row["backtest_run_id"]),
        verdict=ResearchVerdict(str(row["verdict"])),
        artifact_path=root / str(relative) if relative else None,
        artifact_sha256=str(row["artifact_sha256"]) if row["artifact_sha256"] else None,
        error=str(row["error"]) if row["error"] else None,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExperimentValidationError("experiment clock must return an aware timestamp")
    return value.astimezone(UTC)
