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
- Encrypted offsite backup and external availability notifications still need an operator-selected destination. See the next-step evidence below for Cloudflare, runtime SQL privileges and automation activation; source implementation alone does not prove live operation.
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

## Deployment automation and Cloudflare preparation — 2026-10-05

- Added a canonical Compose wrapper selecting preview/public mode, immutable image release references and optional runtime DB credentials. Plain `docker compose up` is no longer the recommended installed operation because it omits these machine-local choices.
- Added the official cloudflared2026.9.3 image pinned by registry manifest digest, non-root token-file access, readiness check and no host port. Public mode enforces Secure cookies and narrow static proxy trust: cloudflared172.30.26.2, Caddy172.30.27.2 on the API network. VM route inspection found no conflicting172.30.26/27 subnet. The mode helper recreates this project's networks/containers without removing persistent data and restores prior mode after ordinary failed activation.
- The root-managed updater polls successful main CI runs, verifies commit ancestry and OCI revision, pins image digests, and rejects incompatible frontend/backend API contract labels before runtime mutation. It shares the operation lock with backup, checks disk reserve, requires a coordinated backup, waits for health and checks SPA/proxied CSRF. Failure rolls back images only when Flyway history is unchanged; a durable interruption/failure gate pauses subsequent updates. Infrastructure versions/scripts remain deliberately operator-updated.
- New systemd update/backup units were installed and verified on the VM. The daily local backup timer was enabled; next run is2026-10-06 at03:15 Europe/Budapest plus jitter. The update timer remains disabled pending registry access and an actual verified registry rollout. Anonymous GHCR pull failed with unauthorized; public Git source does not imply public packages. Package visibility or a read:packages credential remains the owner's choice.
- Local backup verification writes a COMPLETE marker after checksum/gzip/tar checks. Retention defaults to seven days, deletes only old completed timestamp directories and always preserves the newest complete copy. Legacy/incomplete backups remain for review. Offsite encryption/transport is not implemented by this local retention policy.
- Actual isolated restore rehearsal passed on the VM against backup20261005T175514Z: SQL import, matching-image Flyway startup, three referenced files, login/community/mail/audit APIs and exact sample-document download bytes. Gmail stayed disabled in the isolated restore. Disposable containers/networks/files were removed; production data was not replaced. The preview persistence smoke verification removed its own test post afterward.
- VM Gmail is now enabled and verified: the private password file is root:10001 mode0640; connection test returned204, lastSuccessAt2026-10-05T13:36:37Z, lastError null and no failed messages. Default new-install mail remains disabled in the example configuration.
- A separate runtime account was provisioned on the VM and DML-only grants verified. The activation marker remains absent until a compatible backend with separate Flyway credentials is deployed. Both credentials still reside in the backend container; this is a SQL privilege split, not a separate migration process.
- Cloudflare token was privately installed on the VM root:65532 mode0640. Domain routing/public login verification is still pending at this recorded stage; the token file and credential contents are never committed.
- Local validation passed:13 focused Python tests cover successful-main selection, API compatibility, backup retention, unchanged/changed/unreadable Flyway rollback and failed rollback gates; shell scripts passed bash syntax and ShellCheck; preview and public/runtime Compose combinations validated; pinned cloudflared image was pulled and its native readiness command verified. Actual end-to-end registry updates and public HTTPS behavior require separate live evidence.

## Live VM activation — 2026-10-05 evening

- New backend `7d155fef44438e6da6fab1d0ada46a8a9e02c49b` and frontend `e0c8bdeb94182629bf6f50f54937d6ac7de07b0c` were built and deployed on the VM. Hosted CI and GHCR publication also succeeded: [backend run](https://github.com/bmepilots/backend/actions/runs/37352812488), [frontend run](https://github.com/bmepilots/frontend/actions/runs/37352581856). The running pair currently uses local source-built images recorded in private release.env; registry rollout is not yet activated.
- Flyway V1–V8 are successful. Separate runtime DML and migration connections are active; the runtime account identity/grants were checked. Gmail continues to synchronize successfully with no durable failures after the deployment.
- The staged-upload smoke check passed through the VM gateway: anonymous rejection, CSRF/login, protected routes, per-file upload followed by JSON publication, comment, container recreation, exact downloaded bytes, deletion of only the test post, and logout rejection.
- Public Compose mode is active. MariaDB, backend, Caddy and the pinned cloudflared connector are all healthy; Docker reports no published host ports for any of them. Session cookie flags Secure, HttpOnly and SameSite=Lax were verified. The tunnel is connected, while domain DNS routing and the external HTTPS/login check remain pending user account configuration at this point. A healthy connector alone is not a public-login test.
- Daily local backups are enabled for 03:15 Europe/Budapest plus up to five minutes of jitter. Backup 20261005T175514Z passed an isolated full SQL/application restore, three referenced-file checks and an exact document download check; temporary resources and the production smoke post were removed. Encrypted offsite backup and external alert delivery remain unconfigured.
- Installed update service/timer and 13 operation safety tests passed on Ubuntu, but the update timer stays disabled until GHCR read access is supplied and one registry update succeeds. The root-owned operation directory/lock were hardened. Infrastructure scripts and database engine versions require explicit reviewed installation; only application images follow successful main workflows automatically once enabled.

## Registry rollout and public HTTPS verification — 2026-10-05

- The owner made the backend/frontend GHCR packages public. Anonymous pulls and the updater's immutable-digest, OCI revision and API compatibility checks succeeded; no GitHub credential was installed on the VM.
- Backend dependency patch 7660284d366032c769c2305d0e3481f0cf0f29b3 passed [hosted verification and publication](https://github.com/bmepilots/backend/actions/runs/37354712297). GitHub's authenticated Dependabot query subsequently returned zero open backend dependency alerts. The patch updates Bouncy Castle to 1.85 and jsoup to 1.23.1; this is not a general security-audit claim.
- The actual updater completed a coordinated backup, promoted the compatible registry image pair, and passed health/SPA/proxied-CSRF checks. The update timer is now enabled (five minutes after each run plus up to 30 seconds jitter). The persisted release.env/update-state.json are the running-image authority; source build tags are no longer active.
- Cloudflare routing is active: public HTTPS returned the BME Pilots login page and application configuration, and plain HTTP redirected to HTTPS with 301. Session cookies have Secure, HttpOnly and SameSite=Lax. Public HTTPS authentication, protected APIs, staged upload, JSON publication, comments and logout passed through the real tunnel with certificate validation. This API/transport check is distinct from browser visual testing.
- The workstation router DNS at 192.168.0.1 still cached a negative response temporarily, while Cloudflare/Google public resolvers returned the correct edge addresses. During that cache window the operator test explicitly used a freshly resolved Cloudflare edge IP while preserving the real hostname, HTTPS SNI and certificate verification. No hosts-file or persistent DNS setting was changed. Direct home-router WAN IP access is not the application route.
- Final public persistence check passed after recreating the registry-backed backend: exact staged-document bytes/comments survived, the operator test post was deleted, and logout invalidated the session. A new backup of the patched V8 deployment also passed an isolated restore (SQL/Flyway, login/protected APIs, two referenced mail files; no document remained in that snapshot after test cleanup).
- The router's negative DNS cache expired. A normal HTTPS request from the workstation, using its unchanged system DNS and no address override, returned 200 for /login. Cloudflare configuration and local hostname resolution are both verified. The smoke client identifies itself as BMEPilotsDeploymentCheck/1.0; the generic Python user agent had been rejected by the edge.

## Admin password feature deployment (2026-10-09)

- Backend `174c1b44caea69cd119833dead7bd354ef89d6a0` and frontend `5cfc66b7a92d20c31adb285db77d657da3a5065d` passed hosted CI and image publication, then the existing guarded updater deployed the compatible pair. Backend supports contracts `1,2,3`; frontend requires `3`. The final update completed at 09:23:01 UTC (11:23 Europe/Budapest), with its coordinated backup and health/HTTP checks. All four containers are healthy and the timer remains enabled.
- Backend-owned Flyway V9 successfully adds nullable UTC last-login history and backfills matching successful-login audit events. The admin password-reset endpoint revokes target sessions without changing role/status; no duplicate schema or database engine/configuration change belongs in this repository. See backend API/STATUS and frontend STATUS for the feature contract and test evidence.
- Local verification passed 23 backend and 53 frontend tests plus the isolated desktop browser flow. Disposable test services/database were removed, with development database3307 preserved. Public HTTPS returned200 and served the new administration bundle. No production password was reset for verification. The existing Proxmox backup preparation remains a separate, unactivated task.
