# Second-midterm persistence and rollout

The engineering study area now has separate electrical and mechanics midterms. The mechanics bank contains 36 original tasks and three four-task, 100-point mock papers. Content and mathematical provenance are owned by [backend documentation](../../backend/docs/STUDY_MIDTERM_2.md); interactive behavior is documented in the [frontend guide](../../frontend/docs/STUDY_MIDTERM_2.md).

## Schema ownership and compatibility

Backend-owned Flyway **V13__study_midterms.sql** adds `study_attempts.midterm_id VARCHAR(20) NOT NULL DEFAULT '1'` and an index on `(user_id, subject_id, midterm_id, created_at)`. Existing records become first-midterm records without modifying saved request/result JSON, points, IDs or timestamps. Old requests that omit the new field remain first-midterm requests, including UUID replay. Result snapshots preserve historical questions/diagrams and per-field weights; historical omitted weights represent one point.

Progress queries scope totals/history by owner, subject and midterm. Best task scores additionally use the current bank version. The old electrical catalog is unchanged. Mechanics has an independent version; do not update SQL rows to combine these histories or reset users' progress. The default column value exists for compatibility, not permission to omit bank selection in new multi-midterm clients.

No database engine, Compose service, port, volume or secret changes are needed. MariaDB stays Dockerized and internal. Backend advertises API contracts 1–8; the updated frontend requires 8. The existing image-label guard prevents that frontend from being paired with a pre-contract-8 backend.

## Backup and release

1. Let the installed updater select verified compatible immutable images, with its normal settling period and operation lock.
2. Preserve the pre-release coordinated SQL/document/mail-files backup and schema fingerprint. V13 is a schema change, even though it is additive.
3. Verify healthy backend/frontend/database/tunnel containers and successful Flyway V13 after rollout. Check the running OCI revisions and updater state, not just GitHub publication.
4. If health fails after schema change, preserve the existing failure gate and investigate. Never silently downgrade the schema, edit an applied migration, reset the database or remove data volumes.

Current SQL backups automatically include midterm IDs, weighted results and diagrams in result JSON. No new file store is introduced. Restore SQL and both existing file stores together; keep mail disabled during an isolated recovery rehearsal. The source PDFs are private input materials, not new runtime uploads or required production backup files. No Proxmox or unrelated backup draft is changed by this feature.

## Verification boundary

The actual migration is tested against a temporary old-shaped table in the integration MariaDB connection, proving existing rows default to midterm 1 without changing result JSON. API tests verify score totals, legacy replay and cross-member/midterm isolation. Local Docker availability, hosted integration results and production deployment evidence must be recorded separately in STATUS. No real study attempts, emails or member settings should be mutated merely to test a release.
