#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
mountpoint -q /srv/bmepilots || { echo 'Data disk is not mounted.' >&2; exit 1; }
[[ "$(pwd -P)" == /srv/bmepilots/db/deploy ]] || { echo 'Install from /srv/bmepilots/db/deploy.' >&2; exit 1; }
umask 077
[[ ! -L /srv/bmepilots/deploy && ! -L /srv/bmepilots/deploy/operation.lock ]] || { echo 'Operation lock paths must not be symbolic links.' >&2; exit 1; }
install -d -o root -g root -m 0755 /srv/bmepilots/deploy
touch /srv/bmepilots/deploy/operation.lock
chown root:root /srv/bmepilots/deploy/operation.lock
chmod 0600 /srv/bmepilots/deploy/operation.lock
[[ -f .deployment-mode ]] || printf 'preview\n' >.deployment-mode
[[ -f automation.json ]] || cp automation.example.json automation.json
bash scripts/compose.sh config --quiet
# Do not allow a non-root checkout owner to replace scripts executed by systemd.
chown root:root /srv/bmepilots /srv/bmepilots/db . scripts systemd
chmod 0755 /srv/bmepilots /srv/bmepilots/db
chmod 0755 . scripts systemd
find . -maxdepth 1 -type f -exec chown root:root {} + -exec chmod go-w {} +
find scripts systemd -type f -exec chown root:root {} + -exec chmod 0644 {} +
chown root:root .env .deployment-mode automation.json
chmod 0600 .env .deployment-mode automation.json
install -o root -g root -m 0644 systemd/bmepilots-*.service systemd/bmepilots-*.timer /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/bmepilots-{update,backup}.{service,timer}
echo 'Units installed. Run update.py --check and one successful update before enabling timers.'
echo 'Enable with: sudo systemctl enable --now bmepilots-update.timer bmepilots-backup.timer'
