FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock readme.md ./
COPY schema ./schema
COPY src ./src
COPY examples ./examples

RUN uv sync --frozen --no-dev

FROM python:3.12-slim-trixie AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/schema /app/schema
COPY --from=builder /app/src /app/src
COPY --from=builder /app/examples /app/examples
COPY --from=builder /app/readme.md /app/readme.md

RUN useradd --system --create-home --uid 10001 appuser && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["label-sea"]
CMD ["--help"]