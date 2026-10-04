# Status and handoff

Updated: 2026-10-04. Update this file with every change.

## Implemented
- Dedicated Docker MariaDB repository, internal network and fixed persistent volume.
- Loopback-only development override; generated local secrets.
- Agent guide, architecture and operations documentation.
- Separate tmpfs integration-test database/project on loopback 3308; no dependency on or deletion of development data.

## Verification
- Initial environment inspection: Docker CLI present; Docker daemon not running.
- Compose validation passed; MariaDB 11.8.8 image pulled and container healthy.
- Docker Desktop cannot forward host ports into an internal-only network here. The dev override sets the network internal flag false and publishes only 127.0.0.1:3307; base Compose remains internal and unpublished.
- Backend successfully connected and applied Flyway V1–V7. Data persisted through a container/network recreation without removing the named volume.
- Real MariaDB integration tests passed on 2026-10-04, including document storage boundaries/rollback, calendar/link relations, audit records and mail synchronization persistence. Test schema is bmepilots_test, development schema is bmepilots.

## Deferred
- Production deployment, separate migration account, scheduled encrypted offsite backup.
- No application schema here: backend Flyway owns it.
- Uploaded document files and mail attachments are backend-owned private stores and must be backed up together with MariaDB; this repository only provides the database volume.
