FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock readme.md ./
COPY schema ./schema
COPY src ./src
COPY examples ./examples

RUN uv sync --frozen --no-dev

ENTRYPOINT ["label-sea"]
CMD ["--help"]