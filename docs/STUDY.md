# Exam prep persistence and operations

Updated: 2026-10-13.

The new `/study` area is an application feature. Docker MariaDB remains the sole database; there is no browser-only progress store, new service or separate database engine.

## Schema and ownership

Backend Flyway migration `V11__study_attempts.sql` creates `study_attempts`. It stores user/request UUIDs, subject ID and catalog version, PRACTICE/MOCK mode, submitted answers, complete question/result snapshots, earned/possible points and a UTC creation timestamp. A unique user/request key makes retries idempotent; a user/subject/time index supports private history. Existing users, mail, documents and forwarding settings are unaffected. Do not copy this DDL into this repository or edit previously applied migrations.

The application image contains the versioned original question bank. The database contains personal submitted attempts and historical question snapshots. Original PowerPoint/JPEG attachments are not uploaded or stored as part of this release. Browser-only unfinished drafts are not backed up because they have not been submitted.

## Backup, restore and capacity

The existing complete MariaDB dump automatically includes `study_attempts`; no backup-table allowlist or new file directory is required. Existing coordinated database/documents/attachments backups remain necessary for the rest of the portal. Restoring a snapshot taken before V11 naturally lacks later study results. A newer compatible backend can migrate that restored schema. Never automatically downgrade schema when rolling back images.

Each attempt stores bounded answers (at most six exercises, 20 fields each, 256 characters per answer) plus original question, circuit and worked-result snapshots. Repeated attempts add rows; storage depends on actual use and is not represented as a fixed measured size. Monitor `information_schema.tables` for the table's data/index sizes as part of normal capacity checks. No automatic attempt retention/deletion job is introduced. These rows contain private educational progress and are covered by the existing private backup access controls.

## Deployment and verification

Backend supports contracts `1,2,3,4,5`; frontend requires `5`. The existing updater must choose a compatible pair and take its normal coordinated backup before rollout. There are no Compose, MariaDB version, SQL privilege, secret mount, Cloudflare or Gmail changes. Runtime SELECT/INSERT/UPDATE/DELETE permissions already cover application tables; Flyway owns creation with its migration credentials.

Verify V11 and application health after a future rollout. For local verification use the isolated `compose.test.yml` tmpfs database on3308, never persistent development3307. Keep `MAIL_ENABLED=false` for tests and restores; study verification does not require sending any email. Source/architecture and exact API behavior are in backend `docs/STUDY.md` and frontend `docs/STUDY.md`. Consult their STATUS files for actual test results and deployment evidence.

The preexisting unactivated Proxmox backup preparation is a separate task and is not changed by this feature.
