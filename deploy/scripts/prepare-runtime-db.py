#!/usr/bin/env python3
"""Provision the runtime DML account; activate only with a compatible backend."""
import os
from pathlib import Path
import re
import secrets
import subprocess

DEPLOY = Path(__file__).resolve().parent.parent


def query(sql, runtime=False):
    if runtime:
        command = ["bash", "scripts/compose.sh", "exec", "-T", "-e", "MYSQL_PWD", "mariadb",
                   "mariadb", "-ubmepilots_runtime", "-h127.0.0.1", "--batch", "--skip-column-names"]
        env = dict(os.environ, MYSQL_PWD=(DEPLOY / "secrets/db_runtime_password").read_text().strip())
    else:
        command = ["bash", "scripts/compose.sh", "exec", "-T", "mariadb", "sh", "-c",
                   'export MYSQL_PWD="$(cat /run/secrets/db_root_password)"; '
                   'exec mariadb -uroot --batch --skip-column-names']
        env = None
    result = subprocess.run(command, cwd=DEPLOY, input=sql, text=True, capture_output=True, env=env)
    if result.returncode:
        # SQL errors could contain the CREATE USER statement; never echo output.
        raise RuntimeError("Database account operation failed; credentials and SQL suppressed")
    return result.stdout.strip()


def main():
    if os.geteuid() != 0 or DEPLOY != Path("/srv/bmepilots/db/deploy"):
        raise RuntimeError("Run with sudo from the installed VM deployment")
    subprocess.run(["mountpoint", "-q", "/srv/bmepilots"], check=True)
    os.umask(0o077)
    import fcntl
    descriptor = os.open("/srv/bmepilots/deploy/operation.lock",
                         os.O_CREAT | os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        settings = dict(line.split("=", 1) for line in (DEPLOY / ".env").read_text().splitlines()
                        if "=" in line and not line.startswith("#"))
        database = settings.get("MARIADB_DATABASE", "bmepilots")
        if not re.fullmatch(r"[A-Za-z0-9_]+", database):
            raise RuntimeError("Unsupported database identifier")
        secret = DEPLOY / "secrets/db_runtime_password"
        exists = query("SELECT COUNT(*) FROM mysql.user WHERE User='bmepilots_runtime' AND Host='%';") == "1"
        if exists and not secret.is_file():
            raise RuntimeError("Runtime account already exists without its local password file; refusing password reset")
        if not secret.exists():
            with secret.open("x", encoding="ascii") as stream:
                stream.write(secrets.token_hex(32) + "\n")
        os.chown(secret, 0, 10001)
        secret.chmod(0o640)
        password = secret.read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", password):
            raise RuntimeError("Runtime credential must be the generated 64-character hexadecimal value")
        if not exists:
            query(f"CREATE USER 'bmepilots_runtime'@'%' IDENTIFIED BY '{password}';\n"
                  f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{database}`.* TO 'bmepilots_runtime'@'%';")
        query("SELECT 1;", runtime=True)
        grants = query("SHOW GRANTS FOR 'bmepilots_runtime'@'%';").splitlines()
        expected = f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{database}`.* TO `bmepilots_runtime`@`%`"
        permitted = [line for line in grants if not line.startswith("GRANT USAGE ON *.* ")]
        if permitted != [expected]:
            raise RuntimeError("Runtime grants differ from expected DML-only policy; review without logging grants")
        print("Runtime account verified with SELECT, INSERT, UPDATE, DELETE only.")
        print("After deploying a compatible backend, enable: sudo touch .runtime-db-enabled")
        print("Then recreate backend using sudo bash scripts/start.sh.")


if __name__ == "__main__":
    main()
