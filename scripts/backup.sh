#!/bin/sh
# Daily backup (SPEC §17): PostgreSQL dump + uploaded files, in one archive
# encrypted with BACKUP_PASSPHRASE (AES-256, openssl), kept BACKUP_KEEP_DAYS
# (30) in BACKUP_DIR and, when BACKUP_REMOTE is set, mirrored with rclone to
# an external storage with the same retention. Restore: scripts/restore.sh.
#
#   0 3 * * * /srv/sobased/scripts/backup.sh >> /var/log/sobased-backup.log 2>&1
set -eu
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f ${COMPOSE_FILE:-docker-compose.prod.yml}"

# .env is not sourced (values may contain shell characters): read the keys.
env_value() { grep -E "^$1=" .env | head -n 1 | cut -d= -f2- ; }
POSTGRES_USER=$(env_value POSTGRES_USER)
POSTGRES_DB=$(env_value POSTGRES_DB)
BACKUP_PASSPHRASE=$(env_value BACKUP_PASSPHRASE)
BACKUP_DIR=$(env_value BACKUP_DIR)
BACKUP_REMOTE=$(env_value BACKUP_REMOTE)
BACKUP_KEEP_DAYS=$(env_value BACKUP_KEEP_DAYS)
BACKUP_DIR=${BACKUP_DIR:-./backups}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-30}
[ -n "$BACKUP_PASSPHRASE" ] || { echo "BACKUP_PASSPHRASE manquant dans .env" >&2; exit 1; }
export BACKUP_PASSPHRASE

STAMP=$(date -u +%Y%m%d-%H%M%S)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$BACKUP_DIR"

# 1. Database, custom format (pg_restore can rebuild it in any order).
$COMPOSE exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$WORK/db.dump"
# 2. Uploaded files (local storage; with S3 the bucket has its own backups).
$COMPOSE exec -T backend tar -C /data/media -cf - . > "$WORK/media.tar"
# 3. One encrypted archive.
ARCHIVE="$BACKUP_DIR/sobased-$STAMP.tar.gz.enc"
tar -C "$WORK" -cf - db.dump media.tar | gzip \
	| openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE -out "$ARCHIVE"
echo "Sauvegarde : $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 4. Retention, local then remote.
find "$BACKUP_DIR" -name 'sobased-*.tar.gz.enc' -mtime "+$BACKUP_KEEP_DAYS" -delete
if [ -n "$BACKUP_REMOTE" ]; then
	rclone copy "$ARCHIVE" "$BACKUP_REMOTE"
	rclone delete --min-age "${BACKUP_KEEP_DAYS}d" "$BACKUP_REMOTE"
	echo "Copie distante : $BACKUP_REMOTE"
fi
