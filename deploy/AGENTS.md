# Deployment maintenance

Read `README.md` here and `../docs/STATUS.md`. All documentation/scripts are English. Keep the three independent repository histories; deployment lives in db, application migrations in backend.

- Base Compose publishes no ports; loopback override is for SSH preview only. Public mode adds Cloudflare and narrow static proxy trust. Use scripts/compose.sh after installation so the selected mode, image digests and runtime override are included. Read STATUS for actual activation evidence.
- Real settings and secrets are machine-local. Never commit them, print secrets in validation output, or include them in a build context/source archive.
- `/srv/bmepilots` is the existing mounted data filesystem. Never format, reset, remove or replace it to solve application issues. Verify mount/UUID before storage work.
- Keep database and document/mail files together in backups. Never use `down -v` on persistent storage. Verify restoration separately; an archive integrity check is not a restore test.
- Backend runs UID/GID 10001. Preserve Linux ownership and file-based secret permissions; Compose secret uid/gid metadata does not fix bind-mounted host ownership.
- Check base/build/loopback/public/runtime Compose combinations, bash syntax, ShellCheck, operation safety tests and actual VM health. Smoke-test login and persistent file bytes when changing gateways, permissions or mount layout. The operator smoke script creates/removes only its own test post and uses the bootstrap credential before password rotation; its default URL is private preview.
- Never execute fetched Git scripts as root. The updater resolves successful main metadata, verifies API contract/OCI revision labels and pulls immutable images. Preserve the operation lock, backup, Flyway rollback gate and update-failure.json until an operator investigates. Maintain image API contract labels when compatibility changes.
- Retention may remove only completed timestamp backups older than policy and must preserve the newest completed backup. Restore rehearsal uses disposable isolated resources; never clean or restore over live application paths.
- Update README and db/docs/STATUS.md with actual commands/outcomes and unresolved work. Keep backend/frontend STATUS synchronized when their images or runtime behavior change.
