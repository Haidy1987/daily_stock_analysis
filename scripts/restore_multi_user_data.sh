#!/usr/bin/env bash
# Restore a backup created by scripts/backup_multi_user_data.sh.
# Requires the application to be stopped. Does not start services.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${1:-}"
DEST_DATA="${2:-${ROOT_DIR}/data}"

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}/data" ]]; then
  echo "usage: $0 <backup_dir> [dest_data_dir]" >&2
  echo "example: $0 backups/multi-user-20260101120000" >&2
  exit 1
fi

if [[ -d "${DEST_DATA}" ]]; then
  SAFETY="${DEST_DATA}.pre-restore.$(date +%Y%m%d%H%M%S)"
  echo "moving existing data to ${SAFETY}"
  mv "${DEST_DATA}" "${SAFETY}"
fi

mkdir -p "$(dirname "${DEST_DATA}")"
cp -a "${BACKUP_DIR}/data" "${DEST_DATA}"

if [[ -f "${BACKUP_DIR}/config/dotenv.env" ]]; then
  echo "note=Found backup dotenv at ${BACKUP_DIR}/config/dotenv.env"
  echo "note=Restore it manually if needed: cp ${BACKUP_DIR}/config/dotenv.env .env"
fi

echo "restore_ok dest=${DEST_DATA}"
echo "next=Start the previous or compatible app image, then verify /api/v1/health and admin login."
