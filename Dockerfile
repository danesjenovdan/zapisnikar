FROM python:3.14

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN mkdir /app
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
	UV_LINK_MODE=copy \
	UV_PYTHON_DOWNLOADS=0 \
	UV_PROJECT_ENVIRONMENT=/opt/venv \
	PATH="/opt/venv/bin:$PATH"

# Install dependencies first (cached separately from app code changes).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
	uv sync --locked --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
	uv sync --locked --no-dev

# RUN python3 manage.py compilemessages

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

# ENV DJANGO_SETTINGS_MODULE=parladata_project.settings.k8s

CMD exec python manage.py runserver 0.0.0.0:8000
