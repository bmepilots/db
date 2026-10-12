# Shared-mail forwarding operations

Updated: 2026-10-12.

## Ownership and deployment

The backend owns the SMTP sender, durable delivery queue and Flyway V10. The frontend owns the administrator control under **Admin → Email connection → Automatic forwarding**. This repository continues to own Docker MariaDB, the installed Compose configuration and coordinated backups. Do not duplicate application SQL in MariaDB initialization scripts.

The compatible images declare backend API contracts `1,2,3,4` and frontend requirement `4`. The existing guarded updater can install the application images after successful `main` CI without an infrastructure rollout. The installed Gmail settings already provide `MAIL_ENABLED`, `MAIL_USERNAME` and the mounted `MAIL_PASSWORD_FILE`. Forwarding reuses those credentials; no new password or public inbound port is required. The backend's existing egress network must permit outbound TLS to Gmail SMTP, in addition to IMAP.

V10 initializes forwarding **disabled**. Publishing or deploying the feature must not enable it or send historical mail. An administrator enables it in the application after the compatible release is available. Configuration availability is not proof that SMTP authentication or delivery has succeeded; inspect the delivery counters and errors after a genuine incoming message.

## Delivery behavior

Only newly imported eligible messages received after the current enable time are queued. The recipient list is selected from current ACTIVE accounts for each message, so newly approved or reactivated members automatically receive future mail without maintaining a separate list. Old messages are not resent when membership changes. Pending, rejected, suspended and disabled members are excluded; membership is checked again before sending. The shared mailbox itself is excluded to prevent a forwarding loop.

Each member receives an individual copy, with the original sender information, message content and imported attachments. Community recipient addresses are not exposed as a mailing list. Existing import size/type restrictions still apply. Mail that could not be imported cannot be forwarded; inspect both import failures and forwarding failures.

Disabling forwarding cancels queued work. A delivery already in progress cannot be recalled. Re-enabling starts a new eligibility window, rather than replaying the old queue. Delivery state is durable and ordinary import replays do not create another delivery for the same message/member pair. An interrupted or ambiguous SMTP submission is not automatically retried because the provider may already have accepted it. Inspect such cases before manually contacting recipients; SMTP cannot promise exactly-once delivery across a crash.

Forwarding is separate from members' private read/important flags and does not mark Gmail messages read. Original inbox messages remain available in the portal regardless of the forwarding toggle. See [backend mail documentation](../../backend/docs/MAIL.md) for exact retry timing, loop detection, state transitions and API details.

## Provider limits and troubleshooting

Personal Gmail applies sending limits; distributing each incoming message to every active member consumes multiple outgoing messages. Google documents that sending more than 500 emails in a day can trigger a temporary restriction. This is not a guaranteed quota: delivery, anti-abuse and account restrictions can apply earlier. See [Google's sending limits](https://support.google.com/mail/answer/22839?hl=en) and [SMTP error reference](https://support.google.com/mail/answer/3726730?hl=en).

If sending fails, inspect the safe error code and counts in the admin panel, then verify secret-file permissions, account access and outbound SMTP connectivity using the backend runbook. Do not print the App Password, dump private message bodies or use a broadcast to all members as a connectivity test. The existing **Test connection** action checks IMAP; it is not an SMTP-delivery test. Failed and uncertain deliveries need operator attention after bounded automatic retries; toggling forwarding does not resend them.

## Backup and restore

The existing full application database dump includes the forwarding setting, enable cutoff, queue and delivery history. Forwarded attachments use the existing private mail attachment store; no additional filesystem volume is introduced. Keep the database and both current file stores together, with the exact application image references.

Stopping the backend during a coordinated backup also pauses forwarding. Normal restart preserves queued/sent history; uncertain in-flight work is retained for review instead of blind resubmission. An older database restore is different: it can forget mail already accepted after the snapshot and cannot undo email delivered externally.

Always start a restored instance with `MAIL_ENABLED=false`, including when the restored forwarding setting says enabled. Before reconnecting production mail, turn forwarding off through the admin API/UI and reconcile restored delivery history against provider evidence. Do not automatically resume an old queue after disaster recovery. A deliberate later enable creates a fresh cutoff. Keep the existing isolated restore rehearsal's Gmail-disabled environment; never send mail from a restored test copy.

## Verification boundary for this release

The implementation passed local database, API, MIME, frontend and desktop browser checks with fake mail delivery. SSH was unavailable during implementation on October 9–10 and became available again on October 12 for release verification. Actual hosted CI and server rollout results are recorded in STATUS; image publication alone is not proof of a VM deployment or successful SMTP delivery. Keep the live forwarding toggle off during release verification: neither a source deployment nor a health check should broadcast mail to members.
