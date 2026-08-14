"""Static safety contracts for repository and container infrastructure."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compose_service_is_isolated() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    required_controls = (
        "ATL_MODE: RESEARCH",
        "network_mode: none",
        "read_only: true",
        'user: "10001:10001"',
        "no-new-privileges:true",
        "cap_drop:",
        "- ALL",
    )
    for control in required_controls:
        assert control in compose
    assert "ports:" not in compose


def test_public_data_service_is_explicit_and_persistent() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "profiles: [data]" in compose
    assert "ATL_DATA_ROOT: /data" in compose
    assert "market-data:/data" in compose
    assert "market-data:" in compose
    for secret_name in ("API_KEY", "API_SECRET", "PASSWORD", "TOKEN"):
        assert secret_name not in compose


def test_experiment_service_is_offline_and_persistent() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "profiles: [experiments]" in compose
    assert "ATL_MODE: BACKTEST" in compose
    assert "research-artifacts:/artifacts" in compose
    assert "research-artifacts:" in compose
    assert "network_mode: none" in compose
    assert "mkdir /data /artifacts" in dockerfile
    assert "chown atl:atl /data /artifacts" in dockerfile


def test_container_runs_unprivileged_and_exposes_no_port() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.14-slim-bookworm\n")
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile
    assert "EXPOSE" not in dockerfile


def test_local_secret_and_data_files_are_ignored() -> None:
    patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
    assert {
        ".env",
        ".env.*",
        "/data/",
        "artifacts/",
        "/backtests/",
        "/experiments/",
        "models/",
        "*.parquet",
        "*.sqlite3",
    } <= patterns
    assert "!.env.example" in patterns


def test_example_environment_is_safe() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ATL_MODE=RESEARCH" in example
    assert "LIVE" not in example
    for secret_name in ("API_KEY", "API_SECRET", "PASSWORD", "TOKEN"):
        assert secret_name not in example
