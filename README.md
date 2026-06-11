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
