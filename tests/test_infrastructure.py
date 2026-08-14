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


def test_container_runs_unprivileged_and_exposes_no_port() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.14-slim-bookworm\n")
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "EXPOSE" not in dockerfile


def test_local_secret_and_data_files_are_ignored() -> None:
    patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
    assert {".env", ".env.*", "data/", "artifacts/", "models/", "*.parquet"} <= patterns
    assert "!.env.example" in patterns


def test_example_environment_is_safe() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ATL_MODE=RESEARCH" in example
    assert "LIVE" not in example
    for secret_name in ("API_KEY", "API_SECRET", "PASSWORD", "TOKEN"):
        assert secret_name not in example
