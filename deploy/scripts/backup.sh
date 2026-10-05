#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
mountpoint -q /srv/bmepilots || { echo 'Data disk is not mounted.' >&2; exit 1; }
umask 077
exec 9>/srv/bmepilots/deploy/operation.lock
flock -n 9 || { echo 'Another operation is running.' >&2; exit 1; }
backup_dir="/srv/bmepilots/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$backup_dir"
resume=false
if [[ -n "$(docker compose ps --status running -q backend)" ]]; then
  resume=true
fi
finish() { if "$resume"; then docker compose start --wait --wait-timeout 180 backend; fi; }
trap finish EXIT
docker compose stop backend
docker compose exec -T mariadb sh -c 'export MYSQL_PWD="$(cat /run/secrets/db_root_password)"; exec mariadb-dump -uroot --single-transaction --routines --events --triggers --databases "$MARIADB_DATABASE"' | gzip >"$backup_dir/database.sql.gz"
tar -czf "$backup_dir/files.tar.gz" -C /srv/bmepilots documents attachments
docker compose images --format json >"$backup_dir/images.json"
(cd "$backup_dir" && sha256sum database.sql.gz files.tar.gz images.json >SHA256SUMS)
echo "Backup created: $backup_dir (local only; keep an encrypted offsite copy)."
