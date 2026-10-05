# BME Pilots 2026 · Database

Docker MariaDB infrastructure and the canonical full-stack Ubuntu VM deployment for the **unofficial BME Professional Pilot 2026 community portal**. This is one of three independent sibling repositories (`db`, `backend`, `frontend`). The domain is bmepilots2026.com. Deployment supports SSH preview and Cloudflare HTTPS, automatic verified application images, local backup scheduling and separate runtime SQL privileges. See `docs/STATUS.md` for actual activation/run evidence.

## Start on Windows

Prerequisites: Docker Desktop running with Linux containers, Docker Compose v2, PowerShell 7.

```powershell
cd C:\Users\user\Desktop\bmepilots\db
pwsh -File scripts/setup.ps1
docker compose -f compose.yml -f compose.dev.yml config --quiet
docker compose -f compose.yml -f compose.dev.yml up -d --wait
docker compose ps
```

Setup refuses to overwrite an existing `.env`. It generates independent random root and application passwords. Do not paste them into issues or commit them. The backend development script reads this sibling `.env` without printing the credentials.

The base Compose publishes **no ports** and uses an internal network. The local override publishes only `127.0.0.1:3307` and permits bridge egress so Docker Desktop can forward that port; it is needed while Java runs on the host. Never change the binding to `0.0.0.0`.

## Ubuntu VM deployment

[`deploy/README.md`](deploy/README.md) is the canonical deployment runbook. `deploy/` replaces the earlier unversioned deployment draft and owns the full stack: MariaDB, the backend Java image, and the frontend static Caddy image/gateway. The sibling application repositories own their Dockerfiles; backend Flyway remains the sole owner of application schema.

- `deploy/compose.yml` publishes no host ports. MariaDB joins only the internal database network; backend joins internal API/database networks and an egress network for Gmail IMAP. The frontend gateway proxies same-origin `/api/*` requests.
- `deploy/compose.build.yml` builds from the sibling backend/frontend checkouts when locally built images are needed.
- `deploy/compose.loopback.yml` publishes only gateway `127.0.0.1:8088` on the VM and uses non-Secure cookies for a temporary SSH-forwarded HTTP preview. Never expose this override's HTTP service publicly.
- `deploy/scripts/prepare.sh` runs as root, verifies `/srv/bmepilots` is mounted, preserves existing secrets, prepares persistent paths and assigns backend UID/GID `10001` permissions. It also makes the dedicated VM's Docker service require that mount.
- `deploy/scripts/start.sh` verifies the mount, validates Compose without printing expanded secrets, starts the chosen configuration and waits for healthy services. Pass the same Compose file selection on later operations.

VM persistence uses bind directories on `/srv/bmepilots`: `mariadb`, `documents`, `attachments`, `logs` and `backups`. These are separate from the development named volume below. Credentials live in ignored deployment secret files; backend-readable files use `root:10001` and mode `0640`, and the root database password remains `root:root` mode `0600`. Never put passwords in the image or committed configuration. Preparation does not format or reset the data disk.

`deploy/compose.public.yml` supplies Cloudflare and narrow proxy trust; `compose.runtime-db.yml` separates runtime/migration credentials after explicit provisioning. The updater follows successful main workflows, checks API contract/revision labels and uses immutable image digests with backup/health/rollback guards. Daily local backups retain seven days by default and always keep the newest completed copy. Infrastructure versions/configuration are deliberately updated by an operator. Encrypted offsite copies and external health notifications need further configuration. Read the deployment runbook before changing installed operations.

## Development persistence and lifecycle

Data lives in the fixed named volume `bmepilots_mariadb_data`. `docker compose stop` stops containers without losing data; `docker compose ... up -d --wait` restarts them. Ordinary `down` preserves the volume. **Do not use `down -v`** unless deliberately destroying a disposable environment.

MariaDB initialization environment variables apply only when the data directory is empty. Editing `.env` does not rotate an existing SQL user's password. See `docs/OPERATIONS.md`.

## Schema ownership

Flyway in the backend repository owns users, roles, content, mail and audit schema. Do not add application SQL initialization scripts here. This prevents two conflicting schema histories. The database container can be healthy before application tables exist; the backend creates them on first start.

Community migrations V5–V7 also belong exclusively to the backend: V5 adds document posts/files/comments and copies existing knowledge articles without deleting the archive; V6 adds calendar events and useful-link authorship; V7 extends audit records with safe API request metadata. Existing development data is upgraded by the backend on startup. This repository needs no duplicate schema or volume reset. See backend `docs/DOCUMENTS.md`, `docs/COMMUNITY.md` and `docs/AUDIT.md` for those contracts.

## Files and backups

Document and mail file bytes live outside MariaDB in the backend's private `storage/documents` and `storage/attachments` directories for local development, or `/srv/bmepilots/documents` and `/srv/bmepilots/attachments` in the VM stack. The database stores references and metadata. A complete backup pairs a consistent MariaDB snapshot with both file stores from the same coordinated point; backing up only the database or only the upload directory is incomplete. Follow `docs/OPERATIONS.md` and the deployment runbook before retaining the only copy of important community materials. A backup on the same VM disk is not an offsite copy.

## Isolated integration tests

`compose.test.yml` is a separate Compose project with a tmpfs database on `127.0.0.1:3308`. It has no persistent development volume. The backend's `scripts/test.ps1` starts it and runs tests with database/user `bmepilots_test`. After testing, `docker compose -f compose.test.yml down` removes only this disposable test container; the development volume is unaffected. Test data is intentionally lost when the tmpfs container stops.

## Documentation map

- `AGENTS.md`: maintenance rules for humans and agents.
- `docs/ARCHITECTURE.md`: topology, responsibilities and data conventions.
- `docs/OPERATIONS.md`: maintenance, troubleshooting, backup and recovery.
- `docs/STATUS.md`: verified state, limitations and next steps; update on every change.
- `deploy/README.md`: canonical Ubuntu VM deployment, Cloudflare, updates and recovery runbook.
