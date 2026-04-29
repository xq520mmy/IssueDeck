FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8765

VOLUME ["/app/data", "/app/projects"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["issuedeck", "serve", "--config", "server.toml", "--host", "0.0.0.0"]
