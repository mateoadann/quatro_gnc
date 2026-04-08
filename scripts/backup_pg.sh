#!/bin/bash
# ---------------------------------------------------------------------------
# Backup PostgreSQL database before migration to SQLite.
#
# Usage:
#   ./scripts/backup_pg.sh "postgresql://user:pass@host:5432/dbname"
#
# Creates a SQL dump file: backup_YYYYMMDD_HHMMSS.sql.gz
# ---------------------------------------------------------------------------

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <pg_connection_string>"
    echo ""
    echo "Example:"
    echo "  $0 \"postgresql://user:pass@host:5432/dbname\""
    exit 1
fi

PG_URL="$1"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$(cd "$(dirname "$0")/.." && pwd)/backups"
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating PostgreSQL backup..."
echo "  Source:      $PG_URL"
echo "  Destination: $BACKUP_FILE"
echo ""

pg_dump "$PG_URL" | gzip > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup complete: $BACKUP_FILE ($SIZE)"
echo ""
echo "To restore (if needed):"
echo "  gunzip -c $BACKUP_FILE | psql <connection_string>"
