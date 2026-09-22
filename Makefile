# Thin wrappers around docker compose. On Windows (no make): see CLAUDE.md for
# the equivalent commands. Production targets use docker-compose.prod.yml.
.PHONY: up down logs migrate makemigrations test lint format seed shell schema \n	deploy prod-logs backup restore

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

# --- Production (docs/deploy.md) ---------------------------------------------
deploy:
	scripts/deploy.sh

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail 100

backup:
	scripts/backup.sh

# make restore ARCHIVE=backups/sobased-20260923-030000.tar.gz.enc
restore:
	scripts/restore.sh $(ARCHIVE)
