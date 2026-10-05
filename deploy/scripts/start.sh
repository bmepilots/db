#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mountpoint -q /srv/bmepilots || { echo 'Application data disk is not mounted.' >&2; exit 1; }
exec 9>/srv/bmepilots/deploy/operation.lock
flock -n 9 || { echo 'Another operation is running.' >&2; exit 1; }
docker compose "$@" config --quiet
docker compose "$@" up -d --wait --wait-timeout 240
docker compose "$@" ps
