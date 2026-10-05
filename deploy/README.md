# BME Pilots VM operations

Canonical deployment configuration for the three sibling repositories. This directory replaces the earlier unversioned `_deployment-draft`. The current milestone is a private Ubuntu VM deployment with access through an SSH tunnel. Cloudflare, public HTTPS, scheduled deployments and offsite backups are separate milestones; do not treat this preview as a completed public production service.

## Layout and network

```text
/srv/bmepilots/                 mounted ext4 application data disk
  backend/                     backend source/image build context
  frontend/                    frontend source/image build context
  db/deploy/                   this configuration and operator scripts
    .env                       machine-local settings (ignored)
    secrets/                   machine-local credential files (ignored)
  mariadb/                     database files; managed by MariaDB
  documents/                   uploaded document bytes (UID/GID 10001)
  attachments/                 imported mail attachments (UID/GID 10001)
  logs/                        rolling backend logs (UID/GID 10001)
  backups/                     private coordinated backups
  deploy/                      transfer/build logs and operation lock
```

The frontend image contains both Caddy and the compiled SPA. It proxies `/api/*` unchanged to `backend:8080`. The backend connects to MariaDB on the internal `database` network. The internal `backend` network connects Caddy to the API; a separate backend `egress` network permits future Gmail IMAP access. The `edge` network is reserved for frontend access and the future tunnel connector. Only the frontend joins edge. Neither database nor API publishes a host port.

The base Compose file publishes no port and uses secure cookies. `compose.loopback.yml` is the explicit temporary override: only `127.0.0.1:8088` is published and cookies allow HTTP. Never bind this port to all interfaces. Remove the override and recreate the backend with secure cookies before introducing HTTPS through Cloudflare.

## Provision and first start

Prerequisites: Ubuntu, Docker Engine with Compose plugin, source checkouts in the layout above, and the data disk mounted at `/srv/bmepilots`. Do not format storage as part of ordinary deployment. The existing disk is identified by UUID in `/etc/fstab`.

From `/srv/bmepilots/db/deploy`:

```bash
cp .env.example .env             # first use only; never overwrite an existing file
# Edit image references and bootstrap email in .env.
sudo bash scripts/prepare.sh
sudo docker compose -f compose.yml -f compose.build.yml build
sudo bash scripts/start.sh -f compose.yml -f compose.loopback.yml
```

For a local source build set `BACKEND_IMAGE=bmepilots-backend:<unique-release>` and `FRONTEND_IMAGE=bmepilots-frontend:<unique-release>`. For registry deployment use CI-produced SHA tags, preferably pinned digests; do not rely on moving `main` tags for rollback. `compose.build.yml` adds sibling build contexts without changing image names. Build time does not run integration tests; CI verifies them before publishing images.

`prepare.sh` requires root, verifies the mount, creates directories and fresh random credentials only when absent, and preserves existing credentials. Secrets used by the non-root backend are root:10001 mode 0640. The secret directory and database root password are root-only. Compose file-based secrets preserve host file permissions, so changing Compose uid/gid fields alone is insufficient. Use `sudo docker compose` for this deployment. Do not copy development passwords or databases into the VM.

This dedicated VM also gets `/etc/systemd/system/docker.service.d/bmepilots-storage.conf` with `RequiresMountsFor=/srv/bmepilots`. Docker must wait for the data mount at boot. Bind mounts use `create_host_path: false` and `start.sh` checks the mount again, preventing an accidental fresh database on the root disk. Do not remove the dependency while persistent containers use this mount.

## Access and credentials

On the workstation:

```bash
ssh -N -L 127.0.0.1:8088:127.0.0.1:8088 bmepilots@192.168.1.170
```

Keep the SSH session open and browse `http://localhost:8088/login`. Use localhost for this preview and 127.0.0.1 for development on port 5173: browser cookies are shared across ports, so different hostnames avoid the two independent sessions overwriting each other. The first administrator email is configured by `BOOTSTRAP_ADMIN_EMAIL`; the password is in `secrets/bootstrap_admin_password` on the VM. View it only in your own secure terminal with sudo, then change it through `/account`. Clear `BOOTSTRAP_ADMIN_EMAIL` afterward. Keep the referenced secret file while Compose mounts it; removing it breaks startup. Bootstrap never resets an existing admin. Registration starts closed.

VM mail is disabled initially. To enable it later, supply the Gmail App Password in `secrets/mail_app_password`, preserve root:10001 mode 0640, and set `MAIL_ENABLED=true` and `MAIL_USERNAME`. Never print credentials in logs, bake them into images or put them in frontend variables. The egress network is ready; an enabled flag alone does not prove Gmail connectivity.

## Validation and restart

```bash
sudo docker compose -f compose.yml -f compose.loopback.yml config --quiet
sudo docker compose ps
sudo docker compose logs --tail 80 backend
sudo python3 scripts/smoke.py create
sudo docker compose -f compose.yml -f compose.loopback.yml up -d --force-recreate --wait
sudo python3 scripts/smoke.py verify
```

The smoke check logs in without printing credentials, verifies protected APIs, uploads one test document/comment, and verifies its bytes after container recreation. The verify phase removes only that test post. Use it before changing the bootstrap password; afterward it intentionally cannot authenticate using obsolete credentials. It verifies HTTP/API behavior, not visual browser rendering. In-memory sessions end when the backend restarts.

Compose healthchecks gate startup. Restart policies restart exited processes after failure/boot, but an `unhealthy` status alone does not trigger a restart. Monitor health and logs. The backend heap is capped relative to its 1536 MiB container limit. Operational file and Docker log rotation are bounded; SQL audit data and user uploads need capacity monitoring and a future retention policy.

## Backup and recovery

```bash
sudo bash scripts/backup.sh
```

The script acquires an operation lock, stops the backend to pause API writes/mail ingestion, dumps MariaDB consistently, archives both file stores and records image references/checksums. It restarts the existing backend container even if backup fails. This causes a short maintenance window and logs users out. Backups stay root-only under `/srv/bmepilots/backups/<UTC timestamp>`. A partial directory after failure is not a valid backup. Docker image references and source revisions must remain available for recovery.

Check `SHA256SUMS`, gzip integrity and the matching file archive before copying backups offsite. The local data disk is not an offsite backup; scheduling, encryption, offsite destination and a full restore rehearsal remain required before important real data is retained. Restore into a separate test database and file directories using the matching images, with Gmail disabled. Verify login, files/comments/calendar/mail/audit before considering any production replacement. Never overwrite a live database during a rehearsal. See `../docs/OPERATIONS.md` for the recovery contract.

## Updates and remaining public-launch work

Make a coordinated backup before any application/schema update. Pull a compatible backend/frontend image pair, record previous image digests, then `up -d --wait` with the same override set. Use `start.sh` for the mount check. Do not change database passwords by editing secret files: MariaDB initialization variables are effective only on an empty data directory. Database changes need explicit SQL password rotation.

An old application image may be incompatible with a migrated database. Do not automatically downgrade MariaDB or undo Flyway migrations. Use backward-compatible migrations, or perform a deliberate restore of the matching database and file snapshot. Never run `down -v` or delete storage to fix startup errors.

Before public launch: configure the domain/tunnel and trusted proxy behavior, secure cookies/TLS, separate migration/runtime SQL privileges, review rate limiting, implement uploads that fit the chosen Cloudflare request limit, encrypted scheduled offsite backups with restore rehearsal, and health notifications. Current Caddy/Spring allow a 251 MiB request (five 50 MiB files); a Cloudflare 100 MB per-request limit requires a per-file upload flow. CI image publication is prepared separately; this VM does not yet automatically follow `main`.
