# Deployment maintenance

Read `README.md` here and `../docs/STATUS.md`. All documentation/scripts are English. Keep the three independent repository histories; deployment lives in db, application migrations in backend.

- The VM is private: base Compose publishes no ports; loopback override is for SSH preview only. Cloudflare/public TLS and automated rollout are not yet installed.
- Real settings and secrets are machine-local. Never commit them, print secrets in validation output, or include them in a build context/source archive.
- `/srv/bmepilots` is the existing mounted data filesystem. Never format, reset, remove or replace it to solve application issues. Verify mount/UUID before storage work.
- Keep database and document/mail files together in backups. Never use `down -v` on persistent storage. Verify restoration separately; an archive integrity check is not a restore test.
- Backend runs UID/GID 10001. Preserve Linux ownership and file-based secret permissions; Compose secret uid/gid metadata does not fix bind-mounted host ownership.
- Check base/build/loopback Compose combinations, bash syntax and actual VM health. Smoke-test login and persistent file bytes when changing gateways, permissions or mount layout. The operator smoke script creates/removes only its own test post and uses the bootstrap credential before password rotation.
- Update README and db/docs/STATUS.md with actual commands/outcomes and unresolved work. Keep backend/frontend STATUS synchronized when their images or runtime behavior change.
