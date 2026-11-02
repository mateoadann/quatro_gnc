#!/usr/bin/env bash
# Dump the Postgres DB and upload it to Cloudflare R2 (S3 API).
# Needs: DATABASE_URL_UNPOOLED, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
set -euo pipefail

BUCKET="quatro-gnc-backups"
KEY="$(date -u +%Y%m%dT%H%M%SZ).dump"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

pg_dump -Fc --no-owner --dbname "$DATABASE_URL_UNPOOLED" --file "$TMP"

AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" AWS_DEFAULT_REGION=auto \
  AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required \
  aws s3 cp "$TMP" "s3://$BUCKET/$KEY" --endpoint-url "$R2_ENDPOINT" --only-show-errors

SIZE="$(du -h "$TMP" | cut -f1)"
echo "Uploaded $KEY ($SIZE)"
[ -z "${GITHUB_OUTPUT:-}" ] || echo "summary=$KEY ($SIZE)" >> "$GITHUB_OUTPUT"
