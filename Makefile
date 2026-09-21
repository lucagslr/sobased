# Thin wrappers around docker compose. On Windows (no make): see CLAUDE.md for
# the equivalent commands. backup / restore / deploy arrive in phase 14.
.PHONY: up down logs migrate makemigrations test lint format seed shell schema

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail 100

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

test:
	docker compose exec backend pytest
	docker compose exec frontend npm run test

lint:
	docker compose exec backend sh -c "black --check . && isort --check . && flake8"
	docker compose exec frontend npm run lint

format:
	docker compose exec backend sh -c "black . && isort ."
	docker compose exec frontend npm run format

# Regenerate the OpenAPI schema, then the TypeScript types of the front.
schema:
	docker compose exec backend python manage.py spectacular --file openapi/schema.yml
	docker compose exec frontend npm run gen:api

seed:
	docker compose exec backend python manage.py seed_demo

shell:
	docker compose exec backend python manage.py shell
