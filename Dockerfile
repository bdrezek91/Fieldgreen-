FROM python:3.12.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.33 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH=/app/.venv/bin:$PATH \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TZ=UTC

WORKDIR /app

RUN groupadd --gid 10001 atl \
    && useradd --uid 10001 --gid atl --no-create-home --shell /usr/sbin/nologin atl \
    && mkdir /data \
    && chown atl:atl /data

COPY pyproject.toml uv.lock README.md /app/
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=atl:atl src/ /app/src/

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-m", "ai_trading_lab", "status", "--healthcheck"]

CMD ["python", "-m", "ai_trading_lab", "service"]
