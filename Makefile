.PHONY: run migrate test lint vite-dev vite-build docker-up docker-down shell prod-up prod-down prod-logs prod-build

run:
	python manage.py runserver

vite-dev:
	cd frontend && npx vite

vite-build:
	cd frontend && npx vite build

migrate:
	python manage.py makemigrations
	python manage.py migrate

test:
	pytest --cov=apps -x -v

lint:
	ruff check apps/ config/

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Production stack (full app: web, worker, db, redis) — needs .env.prod
prod-build:
	docker compose -f docker-compose.prod.yml build

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

shell:
	python manage.py shell_plus
