# Database repository agent guide

Write documentation and operator-facing script output in English. Application-facing defaults must be English; the user may converse in Hungarian.

Read `README.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, and `docs/STATUS.md`. Update all affected docs and STATUS with every change; list tests actually run and unresolved risks.

- This repository owns local Docker MariaDB infrastructure, not application schema.
- Application DDL is owned exclusively by Flyway in `../backend/src/main/resources/db/migration`.
- Keep MariaDB on an internal Docker network. A development-only override may publish to 127.0.0.1, never 0.0.0.0.
- Persistent named volume; stable project name. Never run `down -v`, remove volumes, reset user databases, or overwrite existing `.env` files without explicit authorization.
- Generate local secrets; do not commit `.env`, dumps or volumes. `.env.example` is a variable reference, not working credentials.
- Document init-only environment variables: changing `.env` does not rotate passwords in an existing volume.
- No cloud deployment, production claims or public DB admin GUI.
- Test schemas are separate from application schema and are clearly named `bmepilots_test`.
