#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
mountpoint -q /srv/bmepilots || { echo 'Data disk is not mounted.' >&2; exit 1; }
umask 077
if [[ "${1:-}" == --lock-held ]]; then
  # Only the updater uses this after acquiring the same exclusive operation lock.
  [[ "${BMEPILOTS_LOCK_HELD:-}" == 1 ]] || { echo 'Missing updater lock context.' >&2; exit 1; }
else
  [[ $# -eq 0 ]] || { echo 'Unknown backup argument.' >&2; exit 1; }
  [[ ! -L /srv/bmepilots/deploy/operation.lock ]] || { echo 'Operation lock must not be a symbolic link.' >&2; exit 1; }
  exec 9>>/srv/bmepilots/deploy/operation.lock
  flock -w 300 9 || { echo 'Another operation is running.' >&2; exit 1; }
fi
compose() { bash scripts/compose.sh "$@"; }
backup_dir="/srv/bmepilots/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$backup_dir"
resume=false
if [[ -n "$(compose ps --status running -q backend)" ]]; then
  resume=true
fi
finish() { if "$resume"; then compose start --wait --wait-timeout 180 backend; fi; }
trap finish EXIT
trap 'exit 1' INT TERM
compose stop backend
compose exec -T mariadb sh -c 'export MYSQL_PWD="$(cat /run/secrets/db_root_password)"; exec mariadb-dump -uroot --single-transaction --routines --events --triggers --databases "$MARIADB_DATABASE"' | gzip >"$backup_dir/database.sql.gz"
tar -czf "$backup_dir/files.tar.gz" -C /srv/bmepilots documents attachments
compose images --format json >"$backup_dir/images.json"
(cd "$backup_dir" && sha256sum database.sql.gz files.tar.gz images.json >SHA256SUMS)
gzip -t "$backup_dir/database.sql.gz"
tar -tzf "$backup_dir/files.tar.gz" >/dev/null
(cd "$backup_dir" && sha256sum --check --quiet SHA256SUMS)
touch "$backup_dir/COMPLETE"
python3 scripts/retain-backups.py
echo "Backup created: $backup_dir (local only; keep an encrypted offsite copy)."
