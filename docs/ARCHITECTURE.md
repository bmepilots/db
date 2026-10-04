# Database architecture

Updated: 2026-10-04.

## Scope and ownership
MariaDB runs exclusively in Docker. This repository supplies infrastructure; backend Flyway supplies application schema; frontend never connects to MariaDB. Compose project name and persistent volume names are fixed to prevent accidental creation of a fresh empty database during path changes.

## Network boundary
Base Compose has a single internal `database` network and no published port. Local override binds TCP 3307 exclusively to IPv4 loopback for a host-run backend and sets the network internal flag to false: Docker Desktop otherwise fails to forward the host port. This development-only bridge allows egress; it does not expose the DB to the LAN. Base Compose remains internal. In a future containerized backend deployment, the backend would join the internal database network and a separate egress network. No such deployment is implemented here.

## Data conventions
InnoDB and utf8mb4; the database service uses UTC. SQL migrations, indexes, constraints and UUID representation are documented in backend `docs/ARCHITECTURE.md`. Activity createdAt/updatedAt timestamps are UTC DATETIME values. Calendar startsAt/endsAt deliberately store Europe/Budapest civil time in DATETIME without implicit timezone conversion, with all-day end dates exclusive. Do not convert these calendar columns as if they were UTC instants.

All application tables are managed by Flyway. Never use application root credentials; the app uses the database-scoped account initialized by MariaDB. The local account currently also runs migrations; split DDL and runtime privileges before production.

## Community schema and storage

Backend migration V5 creates document posts, files and comments, and copies legacy knowledge articles into text-only posts while retaining the original tables. V6 adds calendar events, useful-link author references and a General link category if categories are empty. V7 adds request method, safe route template, status and duration to the audit table. These are backend-owned migrations; do not add matching init SQL or edit applied migrations in this repository.

MariaDB contains document metadata, comments, ownership, versions and private mail flags, but not uploaded file bytes. Backend `storage/documents` and `storage/attachments` (or their configured overrides) form part of the persistent data set. File storage and SQL transactions cannot be one atomic unit; the backend handles ordinary rollback/deletion cleanup, while crash orphan reconciliation remains deferred. Backup/restore must preserve both stores with the matching database, schema version and application revision.

Named user activity and API request metadata are separate views over audit data. No passwords, credentials, cookies, query strings, payloads or document/mail bodies belong in logs. Audit rows have no automatic retention yet; increased request logging will grow the table. Define operational retention and restore testing before production, without deleting audit history ad hoc.

## Versioning
The MariaDB image is pinned to a patch version. Upgrade deliberately: inspect release notes, make and verify a backup, test schema and app against the new image, and document the new version and verification. Never blindly downgrade a data directory.
