#!/usr/bin/env bash
# Recreate only this Compose project's containers/networks; never remove volumes/data.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
mountpoint -q /srv/bmepilots || { echo 'Data disk is not mounted.' >&2; exit 1; }
mode="${1:-}"
[[ "$mode" == public || "$mode" == preview ]] || { echo 'Use set-mode.sh public|preview.' >&2; exit 1; }
if [[ "$mode" == public ]]; then
  [[ -s secrets/cloudflare_tunnel_token ]] || { echo 'Install the tunnel token first.' >&2; exit 1; }
  chown root:65532 secrets/cloudflare_tunnel_token
  chmod 0640 secrets/cloudflare_tunnel_token
fi
[[ ! -L /srv/bmepilots/deploy/operation.lock ]] || { echo 'Operation lock must not be a symbolic link.' >&2; exit 1; }
exec 9>>/srv/bmepilots/deploy/operation.lock
flock -w 300 9 || { echo 'Another operation is running.' >&2; exit 1; }
umask 077
previous=preview
[[ ! -f .deployment-mode ]] || previous="$(cat .deployment-mode)"
[[ "$mode" != "$previous" ]] || { echo "Already configured for $mode; use start.sh."; exit 0; }
# Validate the candidate before stopping a working stack or persisting the new mode.
BMEPILOTS_MODE_OVERRIDE="$mode" bash scripts/compose.sh config --quiet
if [[ "$mode" == public ]]; then
  BMEPILOTS_MODE_OVERRIDE="$mode" bash scripts/compose.sh pull cloudflared
fi
echo "Switching to $mode mode; a short maintenance window is expected."
# Different network address ranges require explicit network recreation.
bash scripts/compose.sh down
printf '%s\n' "$mode" >.deployment-mode
if ! bash scripts/compose.sh config --quiet || ! bash scripts/compose.sh up -d --wait --wait-timeout 300; then
  echo 'Mode activation failed; restoring the previous configuration.' >&2
  bash scripts/compose.sh down || echo 'Candidate cleanup failed; inspect its containers after recovery.' >&2
  printf '%s\n' "$previous" >.deployment-mode
  bash scripts/compose.sh up -d --wait --wait-timeout 300
  exit 1
fi
bash scripts/compose.sh ps
echo "Mode activated: $mode. Verify the externally visible login separately."
