#!/usr/bin/env bash
# Always preserve the installed mode and immutable application image pair.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mode="${BMEPILOTS_MODE_OVERRIDE:-}"
if [[ -z "$mode" ]]; then
  mode=preview
  [[ ! -f .deployment-mode ]] || mode="$(cat .deployment-mode)"
fi
case "$mode" in
  preview) override=compose.loopback.yml ;;
  public) override=compose.public.yml ;;
  *) echo 'Invalid .deployment-mode; expected preview or public.' >&2; exit 1 ;;
esac
args=(--env-file .env)
[[ ! -f release.env ]] || args+=(--env-file release.env)
args+=(-f compose.yml -f "$override")
[[ ! -f .runtime-db-enabled ]] || args+=(-f compose.runtime-db.yml)
exec docker compose "${args[@]}" "$@"
