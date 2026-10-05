# Status and handoff

Updated: 2026-10-05. Update this file with every change.

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
- Public HTTPS/Cloudflare, separate migration account, automated rollout and scheduled encrypted offsite backup remain pending.
- No application schema here: backend Flyway owns it.
- Uploaded documents and mail attachments are persisted alongside MariaDB on the VM data disk, but application storage/schema logic remains backend-owned.

## Private VM deployment — 2026-10-05

- Canonical configuration is versioned in db/deploy; the old _deployment-draft is superseded. Backend and frontend images were built on the Ubuntu 22.04.5 VM with Docker Engine 29.8.2 and Compose 5.6.0.
- MariaDB 11.8.8, backend and frontend are healthy. Caddy serves the SPA and proxies /api from 127.0.0.1:8088; access is through SSH forwarding. No public tunnel is configured.
- Persistent ext4 disk mounted at /srv/bmepilots contains MariaDB, documents, attachments and rolling logs. Docker has a RequiresMountsFor dependency; startup checks mount presence. Existing development DB3307 was not touched.
- VM gateway checks passed: SPA/deep links, anonymous rejection, CSRF/login, authenticated dashboard/community/admin routes, upload/comment creation, logout rejection. Database metadata, comments and exact file bytes survived forced recreation of all three containers; only the test post was then removed.
- Fresh per-VM random secrets were generated without printing passwords. Non-root backend storage ownership and group-readable secret permissions were verified by successful startup/upload. VM Gmail is disabled; local development Gmail settings were not copied.
- A coordinated local backup stopped backend writes, captured MariaDB plus both file stores and image references, and restarted the existing backend. SHA256, gzip and tar integrity passed. Full restore rehearsal, scheduling and encrypted offsite copies are not yet implemented.
- CI workflows passed actionlint 1.7.12/ShellCheck locally. GitHub-hosted execution and image publication subsequently succeeded; the VM currently runs source-built images tagged vm-20261005, not registry images.

- Hosted verification and GHCR publication succeeded: [backend run](https://github.com/bmepilots/backend/actions/runs/37312796111), [frontend run](https://github.com/bmepilots/frontend/actions/runs/37312807646). The VM remains on the verified source-built image pair; image publication alone does not roll out a new version. All three repositories were pushed successfully.
