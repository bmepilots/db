# BME Pilots VM operations

Canonical deployment configuration for the three sibling repositories. This directory replaces the earlier unversioned `_deployment-draft`. It supports private SSH preview, Cloudflare HTTPS, verified main image updates, daily coordinated local backups, and separate runtime/migration SQL users. Configuration being present is not proof of activation: consult `../docs/STATUS.md` for actual live evidence. Encrypted offsite backups and external availability notifications still require an operator-selected destination.

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

The frontend image contains both Caddy and the compiled SPA. It proxies `/api/*` unchanged to `backend:8080`. The backend connects to MariaDB on the internal `database` network. The internal `backend` network connects Caddy to the API; backend `egress` permits Gmail IMAP. In public mode, only frontend and cloudflared join `edge`. Neither database nor API publishes a host port.

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

VM Gmail was enabled and verified on 2026-10-05: the private App Password file is `secrets/mail_app_password` (`root:10001`, mode `0640`), `MAIL_ENABLED=true`, and `MAIL_USERNAME=bmepilots2026@gmail.com`. The admin connection test returned 204 and synchronization reported success without failures. On a new VM, these settings still need explicit configuration; `.env.example` remains disabled by default. Never print credentials in logs, bake them into images or put them in frontend variables. The importer reads Gmail; it does not send messages or change Gmail read flags.

## Validation and restart

```bash
sudo bash scripts/compose.sh config --quiet
sudo bash scripts/compose.sh ps
sudo bash scripts/compose.sh logs --tail 80 backend
sudo python3 scripts/smoke.py create
sudo bash scripts/compose.sh up -d --force-recreate --wait
sudo python3 scripts/smoke.py verify
```

The smoke check logs in without printing credentials, verifies protected APIs, uploads one test document/comment, and verifies its bytes after container recreation. The verify phase removes only that test post. Use it before changing the bootstrap password; afterward it intentionally cannot authenticate using obsolete credentials. It verifies HTTP/API behavior, not visual browser rendering. In-memory sessions end when the backend restarts.

Use `create-staged` in place of `create` to exercise the current per-file upload plus JSON publication protocol. For public checks, run both phases with `sudo env BMEPILOTS_SMOKE_URL=https://bmepilots2026.com python3 scripts/smoke.py <phase>` after DNS and HTTPS are working. The default remains the private HTTP preview URL; Secure session cookies require the public HTTPS URL in public mode.

Compose healthchecks gate startup. Restart policies restart exited processes after failure/boot, but an `unhealthy` status alone does not trigger a restart. Monitor health and logs. The backend heap is capped relative to its 1536 MiB container limit. Operational file and Docker log rotation are bounded; SQL audit data and user uploads need capacity monitoring and a future retention policy.

## Backup and recovery

```bash
sudo bash scripts/backup.sh
```

The script acquires an operation lock, stops the backend to pause API writes/mail ingestion, dumps MariaDB consistently, archives both file stores and records image references/checksums. It restarts the existing backend container even if backup fails. This causes a short maintenance window and logs users out. Backups stay root-only under `/srv/bmepilots/backups/<UTC timestamp>`. A partial directory after failure is not a valid backup. Docker image references and source revisions must remain available for recovery.

The script checks `SHA256SUMS`, gzip integrity and the matching file archive before marking completion. Scheduling is provided below; encryption/offsite transport need a separate destination. `sudo python3 scripts/restore-check.py /srv/bmepilots/backups/<timestamp>` restores into isolated disposable containers/networks and private file paths using the snapshot image IDs, with Gmail disabled. It verifies SQL/Flyway startup, referenced file sizes, login/protected APIs and one document's download bytes, then removes only its disposable resources. Supply `--email` and a private `--password-file` after rotating the bootstrap password. A rehearsal passed on 2026-10-05 with three referenced files and an actual document download; preserve and repeat the check after significant changes. Never overwrite a live database during a rehearsal. See `../docs/OPERATIONS.md` for the recovery contract.

## One command path for installed operations

After installing automation, use `sudo bash scripts/compose.sh ...` for all Compose inspection and maintenance. This wrapper combines `.env`, optional `release.env`, the selected mode, and optional runtime DB privileges. Do not run plain `docker compose up` afterward: it ignores the immutable release pair and mode overrides. `sudo bash scripts/start.sh` delegates to this wrapper and keeps the mount/operation-lock guards.

Machine-local files, all ignored by Git:

| File | Purpose |
| --- | --- |
| `.deployment-mode` | `preview` uses loopback HTTP; `public` uses Cloudflare and Secure cookies. Missing means preview. |
| `release.env` | Exact application image digests currently selected by the updater; overrides only image references in `.env`. |
| `release.previous.env` | Exact previous locally retained image references, for diagnosis and controlled recovery. |
| `.runtime-db-enabled` | Enables the dedicated DML runtime account override. Create only after provisioning and deploying a compatible backend. |
| `automation.json` | Polling deployment policy and local backup retention, initially copied from the documented example. |
| `update-state.json` | Last successful deployment: commits, workflow links, immutable image digests and schema fingerprint. |
| `update-failure.json` | Durable safety gate: an interrupted/failed deployment pauses further automatic changes. |

## Automatic backend/frontend updates

The installed Python updater executes reviewed local code. It never fetches and executes shell scripts from GitHub. Every five minutes it checks each repository's `ci.yml` successful `push` run on `main`, waits at least two minutes after completion, and verifies that the SHA still belongs to main. It pulls the full 40-character commit tag, verifies the OCI revision label, resolves an immutable registry digest, and deploys the resulting pair together. Workflow failure, registry authentication failure, insufficient disk reserve, or another active operation leaves the current application unchanged.

The backend image declares supported API versions in `io.bmepilots.api.contracts` (for example `1,2`) and frontend declares one required version in `io.bmepilots.api.requires` (for example `2`). Unlabeled historical images default to `1`. After pulling both candidates, the updater rejects a mismatched pair before any backup or running-container mutation, so a faster frontend CI cannot overtake its required backend. Maintain these labels whenever API compatibility changes; tests alone cannot infer semantic compatibility. For changes that need a coordinated data transition, disable the timer, deploy a reviewed release and re-enable it after verification. MariaDB, cloudflared, Compose files and operational scripts are updated deliberately from this db repository; they do not automatically change with `main`. This avoids silently changing database engine versions or running repository-provided root commands.

Install from `/srv/bmepilots/db/deploy`:

```bash
sudo bash scripts/install-automation.sh
sudo python3 scripts/update.py --check
sudo python3 scripts/update.py
sudo systemctl enable --now bmepilots-update.timer bmepilots-backup.timer
sudo systemctl list-timers 'bmepilots-*'
```

Installation preserves `.env`, prepares root-owned script/config parent directories, installs and validates systemd units, but does not enable them. `--check` resolves and pulls candidate images without changing running containers. An initial successful manual update is required before enabling the timer. Timers resume after a reboot; the daily backup timer also catches a missed scheduled run. A deployment restarts sessions and can create a short maintenance window.

GHCR packages may be private even when Git repositories are public. A private image requires root's Docker registry credentials. Install a narrowly scoped GitHub PAT with `read:packages` as the private file `secrets/ghcr_read_token`, then authenticate without placing it in command history:

```bash
sudo sh -c 'docker login ghcr.io -u bmepilots --password-stdin < secrets/ghcr_read_token'
```

Keep the token and `/root/.docker/config.json` root-only; Docker stores registry credentials there. Do not change package visibility without the owner's choice. Public GitHub metadata queries work anonymously within GitHub's request limits; an optional root-only `secrets/github_read_token` supplies authenticated metadata access. Rate-limit/network errors stop that update attempt and retry on a future timer tick.

Each changed image pair requires the same operation lock as backups, at least 5 GiB free on both the data and Docker filesystems, a completed coordinated backup, and a recorded Flyway history fingerprint. The updater persists its interruption gate before changing the release file. After `up --wait`, it checks the SPA and proxied CSRF endpoint. Failed health checks restore the exact previous application images **only if Flyway history remains unchanged**. A changed or unreadable history keeps the candidate configuration and requires operator repair/restore, preserving evidence rather than starting old code against unknown schema. No automatic database downgrade or database restore occurs.

```bash
sudo journalctl -u bmepilots-update.service -n 100 --no-pager
sudo systemctl disable --now bmepilots-update.timer  # planned maintenance/pause
sudo cat update-failure.json                        # contains metadata, never secrets
```

After investigating a gate, fix the deployment with the appropriate matching images/schema, verify it, archive `update-failure.json` outside this directory, then rerun the updater and re-enable the timer. Do not repeatedly delete the gate to retry an unexplained failure. A failed unit appears in systemd/journal; external alert delivery is not configured yet. Rollback images and backups consume space; image cleanup is deliberate, and must preserve current, previous and restore-needed image IDs.

## Daily local backup and retention

The backup timer runs at 03:15 Europe/Budapest, with up to five minutes of jitter. A backup pauses the backend (and Gmail importer), captures SQL and both file stores, verifies gzip/tar/checksums, writes `COMPLETE`, then restarts the existing backend even on ordinary backup failure. Daily backup waits up to five minutes for another deployment operation; a busy failure remains visible in systemd. This is a maintenance window and invalidates in-memory logins.

`automation.json` sets `backup_retention_days` (default 7, allowed 1–3650). Only timestamp-named completed local backups older than that age are removed; the newest completed backup is always kept. Incomplete backups, legacy directories without `COMPLETE`, and unrecognized directories are retained for review. Retention runs after a fresh verified snapshot. Encryption/offsite copies are separate required work: local disk failure can destroy both the app and every local backup. Keep secrets/recovery credentials separately; these archives intentionally do not contain credential files.

## Separate runtime and migration SQL privileges

The original database-scoped `bmepilots` account remains the Flyway migration account. Provision a separate `bmepilots_runtime` with only SELECT/INSERT/UPDATE/DELETE:

```bash
sudo python3 scripts/prepare-runtime-db.py
# First deploy a backend version that supports FLYWAY_USER/FLYWAY_PASSWORD_FILE.
sudo touch .runtime-db-enabled
sudo bash scripts/start.sh
```

The helper generates a new private runtime credential, checks the live account/grants and refuses to reset an unknown pre-existing account. It never revokes existing application users or resets MariaDB. `compose.runtime-db.yml` supplies the runtime password to the main datasource and the original password only to Flyway. Both credentials remain mounted in the backend because Flyway runs at startup; this separates SQL connections/permissions, not the container's ability to read the migration credential. A stronger future separation would use an independent migration job. Bootstrap/admin DML still works with the runtime account.

## Cloudflare account steps and public activation

The domain is already owned in the user's Cloudflare account. In the [Cloudflare dashboard](https://dash.cloudflare.com/), go to **Networking → Tunnels**, create a tunnel named `bmepilots2026`, and select the Docker environment. Copy only the token following `--token` from the provided command into a private local file. Do not run a second standalone connector or put the token in Git/chat/history. The operator installs it as `secrets/cloudflare_tunnel_token`, `root:65532`, mode `0640`.

Create the published application route with hostname `bmepilots2026.com`, service type **HTTP**, URL **frontend:80**. A second `www` hostname is optional and should be a redirect or deliberately separate route. Do not route `/api` to the backend directly: all paths go through Caddy. Do not publish database/admin container ports or add home-router port forwarding. Enable **Always Use HTTPS** for the zone and verify the Universal SSL certificate is active. Keep caching rules away from `/api/*`; authenticated responses must never be cached at the edge. The app's own closed registration and session access controls remain necessary.

`compose.public.yml` pins cloudflared 2026.9.3 by manifest digest, uses a token file, read-only filesystem, no capabilities, bounded logs, and a `/ready` health check. No host ports are published. Caddy trusts only connector `172.30.26.2/32`; Tomcat trusts only Caddy `172.30.27.2`. Public networks use `172.30.26.0/28` and `172.30.27.0/28`; check for collisions with VM/Docker/VPN routes before activation. Do not loosen these addresses to every proxy. Public settings require the matching backend/frontend images with trusted proxy support and per-file document uploads.

```bash
sudo bash scripts/prepare.sh                 # existing credentials preserved; token permissions fixed
sudo bash scripts/set-mode.sh public
sudo bash scripts/compose.sh ps
sudo bash scripts/compose.sh logs --tail 30 cloudflared
```

The transition validates the candidate Compose configuration and pulls the pinned connector before stopping the running stack. It then recreates this project's containers and networks with `down` **without `-v`**, preserving all bind data, and restores the previous mode if startup fails. Secure cookies are forced on in public mode, and the HTTP preview binding disappears. A healthy connector proves a Cloudflare connection, not correct DNS, HTTPS redirection or account login: externally verify the domain, actual login redirect/session, logout rejection, document uploads, and client-IP/proto sanitization. Use `set-mode.sh preview` to deliberately return to SSH-only HTTP after investigating a public failure; its network transition also causes downtime.

The installed `/srv/bmepilots/deploy` operation directory is root-owned, and its shared lock is mode `0600`. Preserve that ownership: an unprivileged writer must not be able to replace the inode used by backup, restoration and deployment locks. Lock opens do not truncate the file; installer and shell entry points reject symbolic-link lock paths.

The initial app uploaded up to 250 MiB in one request, exceeding Cloudflare's usual 100 MB request cap. The new compatible frontend/backend must upload each maximum-50-MiB file separately before publishing one post with up to five files. Changing Caddy's local maximum alone cannot bypass the edge limit.

Official references checked 2026-10-05: [tunnel setup](https://developers.cloudflare.com/tunnel/get-started/), [token-file and runtime flags](https://developers.cloudflare.com/tunnel/reference/run-parameters/), [cloudflared release](https://github.com/cloudflare/cloudflared/releases/tag/2026.9.3), [GHCR authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
