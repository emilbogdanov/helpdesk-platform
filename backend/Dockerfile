# syntax=docker/dockerfile:1

FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src

# Dependencies get their own layer, rebuilt only when the lock file changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY . .
# Installed into the virtualenv as a package, so the runtime stage needs no source tree.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM python:3.13-slim
RUN groupadd --system --gid 10001 helpdesk \
    && useradd --system --uid 10001 --gid helpdesk --no-create-home helpdesk
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Files stay owned by root: the app can read its code but not change it. The id is
# numeric so orchestrators can verify it isn't root without resolving names.
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "--factory", "helpdesk.main:app", "--host", "0.0.0.0", "--port", "8000"]
