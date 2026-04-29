#!/usr/bin/env bash
# issuedeck SQLite backup — run on the Docker host.
#
# Produces a consistent snapshot via SQLite's online backup API (safe with WAL
# writers running), then prunes backups older than RETENTION_DAYS.
#
# Uses the issuedeck container itself (has Python + sqlite3), no extra image needed.
#
# Install (on server):
#   chmod +x /opt/issuedeck/scripts/backup.sh
#   crontab -e
#     0 3 * * *  /opt/issuedeck/scripts/backup.sh >> /var/log/issuedeck-backup.log 2>&1

set -euo pipefail

CONTAINER="${ISSUEDECK_CONTAINER:-issuedeck}"
BACKUP_DIR="${ISSUEDECK_BACKUP_DIR:-/opt/issuedeck/backups}"
RETENTION_DAYS="${ISSUEDECK_BACKUP_RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/tracker-$STAMP.db"

# Run .backup inside the running container, then copy out.
docker exec "$CONTAINER" \
    python -c "import sqlite3; sqlite3.connect('/app/data/tracker.db').backup(sqlite3.connect('/tmp/backup.db'))"
docker cp "$CONTAINER":/tmp/backup.db "$OUT"
docker exec "$CONTAINER" rm -f /tmp/backup.db

gzip -9 "$OUT"
echo "[$(date -Is)] wrote ${OUT}.gz ($(du -h "${OUT}.gz" | cut -f1))"

find "$BACKUP_DIR" -name 'tracker-*.db.gz' -mtime +"$RETENTION_DAYS" -print -delete
