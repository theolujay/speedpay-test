ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.19

FROM ${UV_IMAGE} AS uv-image

FROM python:3.13-slim-bookworm AS base

COPY --from=uv-image /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        curl \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY uv.lock pyproject.toml /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

RUN groupadd --system --gid 999 speedpay \
 && useradd --system --gid 999 --uid 999 --create-home speedpay

COPY . /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

RUN python manage.py collectstatic --no-input
RUN chown -R speedpay:speedpay /home/speedpay /app
USER speedpay

FROM base AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group dev
USER speedpay
