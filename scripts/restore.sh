#!/bin/sh
# Restores a backup made by scripts/backup.sh: the database is REPLACED and
# the uploaded files are REPLACED. Stops the app during the operation.
#
#   scripts/restore.sh backups/sobased-20260923-030000.tar.gz.enc
set -eu
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f ${COMPOSE_FILE:-docker-compose.prod.yml}"
ARCHIVE=${1:?usage: restore.sh <archive.tar.gz.enc>}

env_value() { grep -E "^$1=" .env | head -n 1 | cut -d= -f2- ; }
POSTGRES_USER=$(env_value POSTGRES_USER)
POSTGRES_DB=$(env_value POSTGRES_DB)
BACKUP_PASSPHRASE=$(env_value BACKUP_PASSPHRASE)
[ -n "$BACKUP_PASSPHRASE" ] || { echo "BACKUP_PASSPHRASE manquant dans .env" >&2; exit 1; }
export BACKUP_PASSPHRASE

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE -in "$ARCHIVE" | gzip -d | tar -C "$WORK" -xf -
[ -f "$WORK/db.dump" ] && [ -f "$WORK/media.tar" ] || { echo "Archive incomplète." >&2; exit 1; }

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
	printf "Cette restauration REMPLACE la base et les fichiers de %s. Continuer ? [yes/N] " "$POSTGRES_DB"
	read -r answer
	[ "$answer" = "yes" ] || { echo "Annulé."; exit 1; }
fi

$COMPOSE stop backend worker beat
$COMPOSE up -d postgres
# --clean --if-exists drops every object before recreating it; --no-owner
# because the dump was made by the same role anyway.
$COMPOSE exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
	--clean --if-exists --no-owner --exit-on-error < "$WORK/db.dump"
$COMPOSE run --rm --no-deps -T backend sh -c \
	'find /data/media -mindepth 1 -delete && tar -C /data/media -xf -' < "$WORK/media.tar"
$COMPOSE up -d
echo "Restauration terminée depuis $ARCHIVE."
