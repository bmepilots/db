# BME Pilots 2026 · Database

Local MariaDB infrastructure for the **unofficial BME Professional Pilot 2026 community portal**. This is one of three independent sibling repositories (`db`, `backend`, `frontend`). The future domain is bmepilots2026.com. No deployment or Cloudflare configuration is included.

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

## Persistence and lifecycle

Data lives in the fixed named volume `bmepilots_mariadb_data`. `docker compose stop` stops containers without losing data; `docker compose ... up -d --wait` restarts them. Ordinary `down` preserves the volume. **Do not use `down -v`** unless deliberately destroying a disposable environment.

MariaDB initialization environment variables apply only when the data directory is empty. Editing `.env` does not rotate an existing SQL user's password. See `docs/OPERATIONS.md`.

## Schema ownership

Flyway in the backend repository owns users, roles, content, mail and audit schema. Do not add application SQL initialization scripts here. This prevents two conflicting schema histories. The database container can be healthy before application tables exist; the backend creates them on first start.

Community migrations V5–V7 also belong exclusively to the backend: V5 adds document posts/files/comments and copies existing knowledge articles without deleting the archive; V6 adds calendar events and useful-link authorship; V7 extends audit records with safe API request metadata. Existing development data is upgraded by the backend on startup. This repository needs no duplicate schema or volume reset. See backend `docs/DOCUMENTS.md`, `docs/COMMUNITY.md` and `docs/AUDIT.md` for those contracts.

## Files and backups

Document and mail file bytes live outside MariaDB in the backend's private `storage/documents` and `storage/attachments` directories (or DOCUMENT_STORAGE/MAIL_STORAGE overrides). The database stores references and metadata. A complete backup pairs a consistent MariaDB snapshot with both file stores from the same coordinated point; backing up only the Docker volume or only the upload directory is incomplete. Follow `docs/OPERATIONS.md` before retaining the only copy of important community materials.

## Isolated integration tests

`compose.test.yml` is a separate Compose project with a tmpfs database on `127.0.0.1:3308`. It has no persistent development volume. The backend's `scripts/test.ps1` starts it and runs tests with database/user `bmepilots_test`. After testing, `docker compose -f compose.test.yml down` removes only this disposable test container; the development volume is unaffected. Test data is intentionally lost when the tmpfs container stops.

## Documentation map

- `AGENTS.md`: maintenance rules for humans and agents.
- `docs/ARCHITECTURE.md`: topology, responsibilities and data conventions.
- `docs/OPERATIONS.md`: maintenance, troubleshooting, backup and recovery.
- `docs/STATUS.md`: verified state, limitations and next steps; update on every change.
