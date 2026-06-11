.PHONY: run migrate test lint vite-dev vite-build docker-up docker-down shell

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

shell:
	python manage.py shell_plus
