# Database repository agent guide

Write documentation and operator-facing script output in English. Application-facing defaults must be English; the user may converse in Hungarian.

Read `README.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, and `docs/STATUS.md`. Update all affected docs and STATUS with every change; list tests actually run and unresolved risks.

- This repository owns local Docker MariaDB infrastructure and the canonical full-stack Ubuntu deployment in `deploy/`, not application schema. Read `deploy/README.md` before deployment edits.
- Application DDL is owned exclusively by Flyway in `../backend/src/main/resources/db/migration`.
- Keep MariaDB on an internal Docker network. A development-only override may publish to 127.0.0.1, never 0.0.0.0.
- Development uses a persistent named volume; the VM uses bind directories on mounted `/srv/bmepilots`. Keep stable project names and distinct environments. Never run `down -v`, remove volumes, reset user databases, or overwrite existing `.env` files without explicit authorization.
- Generate local secrets; do not commit `.env`, dumps or volumes. `.env.example` is a variable reference, not working credentials.
- Document init-only environment variables: changing `.env` does not rotate passwords in an existing volume.
- The user authorized the private Ubuntu VM container launch. Base deployment publishes no ports; `compose.loopback.yml` publishes only gateway `127.0.0.1:8088` for SSH-forwarded HTTP with non-Secure cookies. Cloudflare/public HTTPS and automatic VM updates remain follow-up work. Never claim deployment or CI verification without actual evidence, and do not expose a public DB admin GUI.
- Preserve mount guards, backend UID/GID 10001 storage access, root-owned private secret files and LF shell scripts. Backend needs egress for Gmail; MariaDB remains on its internal network.
- Keep runtime/migration DB privilege separation, coordinated encrypted offsite backup and restore rehearsal visible as unfinished operational work until implemented and verified.
- Test schemas are separate from application schema and are clearly named `bmepilots_test`.
