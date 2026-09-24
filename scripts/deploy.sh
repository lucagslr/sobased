#!/bin/sh
# First deployment and every update (docs/deploy.md): pull, build, migrate,
# collect Django's static files, restart. Safe to run again at any time.
set -eu
cd "$(dirname "$0")/.."
# ENV_FILE / COMPOSE_PROJECT: only for a local rehearsal (docs/deploy.md §9).
export ENV_FILE=${ENV_FILE:-.env}
COMPOSE="docker compose --env-file $ENV_FILE -p ${COMPOSE_PROJECT:-sobased} -f ${COMPOSE_FILE:-docker-compose.prod.yml}"

[ -f "$ENV_FILE" ] || { echo "$ENV_FILE manquant : copie .env.example et remplis-le." >&2; exit 1; }

if [ "${SKIP_PULL:-}" != "1" ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	git pull --ff-only
fi

$COMPOSE build
$COMPOSE up -d postgres redis
# The media and static volumes must belong to the non-root user of the image
# (they normally do from their first use; this covers a volume created by hand).
$COMPOSE run --rm --no-deps -T --user root backend chown -R app:app /data/media /data/static
# One-off containers: the app containers may not exist yet on a first run.
$COMPOSE run --rm --no-deps -T backend python manage.py migrate --noinput
$COMPOSE run --rm --no-deps -T backend python manage.py collectstatic --noinput --clear
$COMPOSE up -d --remove-orphans
# Django's own deployment checklist (HSTS and the SSL redirect are Caddy's).
$COMPOSE exec -T backend python manage.py check --deploy
$COMPOSE ps
echo "Déploiement terminé."
