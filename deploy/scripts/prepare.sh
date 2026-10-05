#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
mountpoint -q /srv/bmepilots || { echo 'Application data disk is not mounted.' >&2; exit 1; }
umask 077
[[ -f .env ]] || cp .env.example .env
data_root="$(sed -n 's/^DATA_ROOT=//p' .env)"
[[ "$data_root" == /srv/bmepilots ]] || { echo 'Expected DATA_ROOT=/srv/bmepilots.' >&2; exit 1; }
install -d -m 0700 secrets "$data_root/backups"
if [[ ! -d "$data_root/mariadb" ]]; then
  install -d -m 0750 "$data_root/mariadb"
fi
for name in documents attachments logs; do
  install -d -o 10001 -g 10001 -m 0750 "$data_root/$name"
done
for name in db_password db_root_password bootstrap_admin_password; do
  if [[ ! -e "secrets/$name" ]]; then
    openssl rand -hex 32 >"secrets/$name"
  fi
  [[ -f "secrets/$name" && -s "secrets/$name" ]] || { echo "Invalid secret file: $name" >&2; exit 1; }
done
[[ -e secrets/mail_app_password ]] || touch secrets/mail_app_password
for name in db_password bootstrap_admin_password mail_app_password; do
  chown root:10001 "secrets/$name"
  chmod 0640 "secrets/$name"
done
chown root:root secrets/db_root_password
chmod 0600 secrets/db_root_password
# This dedicated VM must not start Docker against empty paths on a missing data disk.
install -d /etc/systemd/system/docker.service.d
printf '[Unit]\nRequiresMountsFor=/srv/bmepilots\n' > /etc/systemd/system/docker.service.d/bmepilots-storage.conf
systemctl daemon-reload
echo 'Storage and secret permissions prepared. Existing secrets preserved.'
