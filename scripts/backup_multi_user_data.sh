#!/usr/bin/env bash
# Backup multi-user runtime data for cutover / rollback.
# Does NOT print .env contents or secrets. Do not commit backup output.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DATA="${1:-${ROOT_DIR}/data}"
STAMP="$(date +%Y%m%d%H%M%S)"
DEST_DIR="${2:-${ROOT_DIR}/backups/multi-user-${STAMP}}"

if [[ ! -d "${SRC_DATA}" ]]; then
  echo "error: data directory not found: ${SRC_DATA}" >&2
  exit 1
fi

mkdir -p "${DEST_DIR}"
# Copy SQLite + WAL companions and local auth artifacts. Exclude caches.
rsync -a --delete \
  --exclude 'cache/' \
  --exclude '*.tmp' \
  "${SRC_DATA}/" "${DEST_DIR}/data/"

# Optional companion files next to data/
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
if [[ -f "${ENV_FILE}" ]]; then
  mkdir -p "${DEST_DIR}/config"
  cp -a "${ENV_FILE}" "${DEST_DIR}/config/dotenv.env"
fi

COMPOSE_FILE="${ROOT_DIR}/docker/docker-compose.yml"
if [[ -f "${COMPOSE_FILE}" ]]; then
  mkdir -p "${DEST_DIR}/config"
  cp -a "${COMPOSE_FILE}" "${DEST_DIR}/config/docker-compose.yml"
fi

{
  echo "created_at=${STAMP}"
  echo "source_data=${SRC_DATA}"
  echo "hostname=$(hostname 2>/dev/null || echo unknown)"
  echo "git_head=$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if command -v docker >/dev/null 2>&1; then
    echo "docker_images=$(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -E 'daily.stock|stock-analysis|dsa' | head -5 | tr '\n' ',' || true)"
  fi
} > "${DEST_DIR}/MANIFEST.txt"

echo "backup_ok path=${DEST_DIR}"
echo "note=Do not commit this directory or paste .env contents into issues/logs."
