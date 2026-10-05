# Local database operations

Updated: 2026-10-05.

## Inspection
Run commands from this repository. Use `docker compose -f compose.yml -f compose.dev.yml ps` and `docker compose logs --tail 100 mariadb`. Avoid printing expanded Compose configuration because environment values contain secrets; use `config --quiet` for validation.

## Start and stop
Start: `docker compose -f compose.yml -f compose.dev.yml up -d --wait`.
Stop: `docker compose stop`.
The healthcheck tests connectivity and InnoDB initialization, not application schema.

## Password rotation
Changing `.env` alone is insufficient after first initialization. Coordinate SQL ALTER USER with backend configuration, using a private operator session and without logging passwords. Root and application passwords are different. Keep existing volumes intact. For development, setup never overwrites existing credentials.

## Backup and restore
Production local backup automation and isolated restore rehearsal are documented in `../deploy/README.md`; encrypted offsite transport still needs an operator-selected destination. Before keeping valuable data, make an InnoDB-consistent `mariadb-dump --single-transaction` of the application database using a protected client options file. Never pass passwords on a command line or commit dumps. Store the dump with matching snapshots of **both** backend file stores: `storage/attachments` (MAIL_STORAGE) and `storage/documents` (DOCUMENT_STORAGE). Include application commit identifiers and Flyway schema version. These directories contain private bytes referenced by SQL rows; neither the dump nor a directory snapshot alone is a complete backup.

Pause mail synchronization and all content writes while coordinating the database and file snapshots; stopping the backend for this local operation is the simplest way to prevent concurrent uploads, deletes and imported attachments. Keep MariaDB running for the consistent dump. Resolve configured storage paths from the backend working directory, and preserve their private access permissions. Encrypt any offsite copy; keep recovery keys separately. Do not copy live database volume files as a substitute for a supported consistent backup.

Restore into a fresh, isolated database first. Import the dump, restore both document and mail files to isolated private directories, configure the matching backend version to use that restored database/storage, and keep live mail polling disabled during the rehearsal. Verify login, document descriptions/comments/authors, document downloads, calendar entries, links, mail attachments and audit history. Check the restored Flyway history before applying any later version. Only then consider replacing working data. A backup is unverified until this test succeeds. Do not restore over the working database as a test.

## Application upgrades and audit growth

The backend applies community migrations V5–V7; this repository does not own their SQL. V5 preserves old knowledge content while creating document tables, V6 adds calendar/link authorship, and V7 extends audit metadata. Back up before applying schema changes to valuable data, start the matching backend, then inspect Flyway validation and application health. Never repair a failed migration by deleting the development volume or changing an already applied migration.

The audit table now records named activity and API request metadata, including reads and denied access. It has no automatic purge/export policy yet. Monitor database size and free disk space, including multipart temporary files and both private backend stores. Operational rolling files under backend `logs/` have separate limits; those limits do not bound the database audit table. Do not remove referenced uploads, run ad hoc audit purges or commit logs/dumps as routine cleanup.

## Integration test environment
Use the distinct `compose.test.yml` (project bmepilots-tests, schema bmepilots_test, loopback port 3308, tmpfs storage). The backend test launcher starts it and supplies the password through process environment. It never reuses the bmepilots_mariadb_data volume. Stop/remove only this temporary environment with `docker compose -f compose.test.yml down` when verification is complete. Never apply that test lifecycle to real data.

## Troubleshooting checklist
- Missing Docker pipe: start Docker Desktop and select Linux containers.
- Port collision: change DB_PORT in `.env`; backend development launcher reads it.
- Access denied after changing `.env`: restore the correct credentials or perform a coordinated SQL rotation; do not delete volumes.
- Database healthy but API fails: inspect backend Flyway errors and schema history.
- Never share logs containing credentials or personal mail.
