# ---- Stage 1: build the Vue/Tailwind assets ----
# Mirror the repo layout (/app/frontend + /app/apps) so the Tailwind
# `@source "../../apps/ui/templates"` directive in src/main.css resolves and
# the Django-template utility classes are NOT purged from the production CSS.
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Django templates referenced by Tailwind's @source — required for the build
# to include classes used outside the Vue components (sidebar, tables, etc.)
COPY apps/ui/templates /app/apps/ui/templates
RUN npx vite build

# ---- Stage 2: application image ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

# Python dependencies (psycopg[binary] ships libpq — no system packages needed)
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# Application code + built frontend assets
COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Bake the static manifest into the image (no DB access needed)
RUN python manage.py collectstatic --noinput

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", "--threads", "2", \
     "--timeout", "60", "--access-logfile", "-"]
