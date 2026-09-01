#!/bin/bash
# Daily DB backup for the Asha Shop stack.
#
# All config comes from /opt/.env (injected by compose). S3/B2 bucket, endpoint
# and credentials can be changed by editing the env file only — no image rebuild.
#
#   S3_BUCKET           (or DB_BUCKET)          bucket name
#   S3_ENDPOINT_URL     (or BACKBLAZE_ENDPOINT_URL)  e.g. https://s3.us-east-005.backblazeb2.com
#   S3_REGION           (or AWS_DEFAULT_REGION)      e.g. us-east-1
#   AWS_ACCESS_KEY_ID   (or BACKBLAZE_ACCESS_KEY)
#   AWS_SECRET_ACCESS_KEY (or BACKBLAZE_SECRET_KEY)
#
# If AWS credentials are missing the dump is still written locally (and a
# warning is shown); S3 upload is skipped.

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/app/backup
mkdir -p "$BACKUP_DIR"

# Resolve env vars (supports both POSTGRES_* and legacy DB_*)
DB_HOST="${POSTGRES_HOST:-${DB_HOST:-db}}"
DB_USER="${POSTGRES_USER:-${DB_USER:-ashauser}}"
DB_PASSWORD="${POSTGRES_PASSWORD:-${DB_PASSWORD:-}}"
DB_NAME="${POSTGRES_DB:-${DB_NAME:-ashadb}}"

# S3 / Backblaze B2 settings
S3_BUCKET="${S3_BUCKET:-${DB_BUCKET:-asha-ai-db-backup}}"
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-${BACKBLAZE_ENDPOINT_URL:-}}"
S3_REGION="${S3_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

# Fallback: Backblaze-style env names -> AWS names (so either naming works)
if [ -n "$BACKBLAZE_ACCESS_KEY" ] && [ -z "$AWS_ACCESS_KEY_ID" ]; then
  export AWS_ACCESS_KEY_ID="$BACKBLAZE_ACCESS_KEY"
fi
if [ -n "$BACKBLAZE_SECRET_KEY" ] && [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  export AWS_SECRET_ACCESS_KEY="$BACKBLAZE_SECRET_KEY"
fi

# Pre-flight checks
if [ -z "$DB_PASSWORD" ]; then
  echo "ERROR: POSTGRES_PASSWORD / DB_PASSWORD is not set. Cannot run pg_dump."
  exit 1
fi

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  echo "WARNING: AWS credentials not set (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)."
  echo "Backup will be created locally but upload will be skipped."
  SKIP_UPLOAD=1
else
  SKIP_UPLOAD=0
fi

# 1. Database Backup (custom format, pg_dump -Fc)
echo "Starting database backup at $DATE"
echo "Host: $DB_HOST | User: $DB_USER | DB: $DB_NAME | Bucket: $S3_BUCKET"

DUMP_FILE="$BACKUP_DIR/db_backup_$DATE.dump"

PGPASSWORD="$DB_PASSWORD" pg_dump \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -F c \
  --no-comments \
  --no-publications \
  --no-subscriptions \
  --no-unlogged-table-data \
  -f "$DUMP_FILE"

if [ ! -f "$DUMP_FILE" ]; then
  echo "ERROR: pg_dump failed - dump file not created."
  exit 1
fi

echo "Backup created: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# 2. Upload to S3
if [ "$SKIP_UPLOAD" -eq 0 ]; then
  echo "Uploading database backup to S3..."
  if [ -n "$S3_ENDPOINT_URL" ]; then
    aws --endpoint-url "$S3_ENDPOINT_URL" s3 cp "$DUMP_FILE" "s3://$S3_BUCKET/db_backup_$DATE.dump" --region "$S3_REGION"
  else
    aws s3 cp "$DUMP_FILE" "s3://$S3_BUCKET/db_backup_$DATE.dump" --region "$S3_REGION"
  fi

  if [ $? -eq 0 ]; then
    echo "Database backup uploaded successfully to S3 bucket: $S3_BUCKET"
  else
    echo "ERROR: Database backup upload failed"
    exit 1
  fi
else
  echo "Skipping S3 upload (credentials missing)."
fi

# 3. Cleanup old local backups (keep last 7 days)
echo "Cleaning up old local backups (older than 7 days)..."
find "$BACKUP_DIR" -name 'db_backup_*.dump' -type f -mtime +7 -delete || true
find "$BACKUP_DIR" -name 'ts_backup_*.dump' -type f -mtime +7 -delete || true

echo "Backup process completed successfully at $(date -u +%Y-%m-%dT%H:%M:%SZ)"