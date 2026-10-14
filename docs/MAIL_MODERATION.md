# Shared mail moderation storage and operations

Updated 2026-10-14. Application schema is owned by backend Flyway migration V12; no SQL is duplicated here.

V12 adds global importance, optimistic moderation version and nullable UTC deletion timestamp to mail_messages. Existing rows start visible and without shared importance; personal read/star rows are unchanged. Backend contract 6 provides admin-only importance/deletion; frontend requires contract 6. Engine, Docker volumes, mount paths and backup scripts are unchanged.

Deletion hides a message, its attachment downloads and unread count from all portal users and cancels queued forwarding. Gmail remains unchanged. Message identity, bodies, attachment rows/bytes, personal state and outbox history remain stored so synchronization cannot reimport the same Gmail message and in-flight delivery does not lose its files. This is not a storage reclamation or privacy-erasure feature. There is no purge/restore endpoint or automatic tombstone expiry.

Normal coordinated backups include all V12 columns and retained bytes. Restoring a snapshot before a deletion also restores its previous visibility; use a matching SQL/file snapshot and observe the existing rule to disable live Gmail/forwarding during restore. Never purge deleted mail or its provider IDs ad hoc: a retention design must preserve deduplication and reconcile outbox/file references. Back up before migration, verify Flyway V12 and health, and do not downgrade schema automatically.

Tests must use the isolated Docker MariaDB on 3308, leaving persistent development3307 and production untouched. Local/hosted verification and rollout evidence are recorded in backend/frontend STATUS. Real user messages must not be deleted or emailed merely to verify this feature.
