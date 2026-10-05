#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mountpoint -q /srv/bmepilots || { echo 'Application data disk is not mounted.' >&2; exit 1; }
[[ ! -L /srv/bmepilots/deploy/operation.lock ]] || { echo 'Operation lock must not be a symbolic link.' >&2; exit 1; }
exec 9>>/srv/bmepilots/deploy/operation.lock
flock -n 9 || { echo 'Another operation is running.' >&2; exit 1; }
if [[ $# -gt 0 ]]; then
  echo 'Explicit Compose selection supplied; ensure it includes current image and runtime overrides.'
  docker compose "$@" config --quiet
  docker compose "$@" up -d --wait --wait-timeout 240
  docker compose "$@" ps
else
  bash scripts/compose.sh config --quiet
  bash scripts/compose.sh up -d --wait --wait-timeout 240
  bash scripts/compose.sh ps
fi
