FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev
COPY src ./src
CMD ["uv", "run", "fastapi", "run", "src/app/main.py", "--host", "0.0.0.0"]
