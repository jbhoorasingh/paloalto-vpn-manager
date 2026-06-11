# VPN Management Platform

VPN Management Platform for Palo Alto firewalls managed by Panorama.

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/)
- [Docker](https://docs.docker.com/get-docker/) (for PostgreSQL and Redis)
- Node.js / npm (for the Vue frontend)

## Quick Start

### 1. Start backing services

```bash
docker compose up -d
```

This starts PostgreSQL (port 5432) and Redis (port 6379).

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` as needed. Defaults work out of the box with the Docker Compose services.

### 3. Install dependencies

```bash
poetry install
cd frontend && npm install
```

### 4. Run migrations

```bash
poetry run python manage.py migrate
```

### 5. Start development servers

You need two terminals:

**Terminal 1 — Django:**
```bash
poetry run python manage.py runserver
```

**Terminal 2 — Vite (frontend hot-reload):**
```bash
cd frontend && npm run dev
```

The app is available at **http://localhost:8000**. Vite serves frontend assets on port 5173 in dev mode.

## Makefile Shortcuts

| Command          | Description                        |
|------------------|------------------------------------|
| `make run`       | Start Django dev server            |
| `make vite-dev`  | Start Vite dev server              |
| `make vite-build`| Build frontend for production      |
| `make migrate`   | Run makemigrations + migrate       |
| `make test`      | Run pytest with coverage           |
| `make lint`      | Run ruff linter                    |
| `make docker-up` | Start Docker services              |
| `make docker-down`| Stop Docker services              |
| `make shell`     | Open Django shell_plus             |

> **Note:** Makefile targets use `python` directly. If your system uses `python3`, either alias it or use `poetry run` commands instead.

## Running Tests

```bash
poetry run pytest
```

## Production Deployment (Docker)

The full stack runs as containers: gunicorn web app (Vue assets and static
files baked into the image, served by WhiteNoise), Celery worker, Postgres
and Redis.

```bash
# 1. Configure secrets (allowed hosts, secret key, DB password, ...)
cp .env.prod.example .env.prod

# 2. Build and start everything
docker compose -f docker-compose.prod.yml up -d --build   # or: make prod-up

# 3. Watch it come up
docker compose -f docker-compose.prod.yml ps
make prod-logs
```

The web container runs migrations on boot (and creates an admin account if
the `DJANGO_SUPERUSER_*` variables are set); the worker waits for a healthy
web container before starting. The app listens on port **8000**.

**TLS:** the stack ships serving plain HTTP (`DJANGO_SECURE_SSL_REDIRECT=False`)
so no certificate is needed to deploy. When a TLS-terminating proxy goes in
front later, flip `DJANGO_SECURE_SSL_REDIRECT=True` and change
`DJANGO_CSRF_TRUSTED_ORIGINS` to the `https://` origin — that one change also
re-enables HSTS and secure-only cookies.

| Command           | Description                                  |
|-------------------|----------------------------------------------|
| `make prod-up`    | Build images and start the production stack  |
| `make prod-down`  | Stop the production stack                    |
| `make prod-build` | Rebuild images only                          |
| `make prod-logs`  | Tail logs from all services                  |

> `docker-compose.yml` (no suffix) remains the local-dev helper that only
> runs Postgres and Redis for `make run`.
