#!/usr/bin/env python3
"""Remove only completed backups older than retention; always keep the newest."""
import datetime as dt
import json
from pathlib import Path
import shutil


def expired_backups(root, days, now):
    completed = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_dir() or not (path / "COMPLETE").is_file():
            continue
        try:
            created = dt.datetime.strptime(path.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        completed.append((created, path))
    completed.sort()
    return [path for created, path in completed[:-1] if created < now - dt.timedelta(days=days)]


def main():
    config = Path(__file__).resolve().parent.parent / "automation.json"
    days = json.loads(config.read_text()).get("backup_retention_days", 7) if config.exists() else 7
    if type(days) is not int or not 1 <= days <= 3650:
        raise ValueError("backup_retention_days must be an integer from 1 to 3650")
    root = Path("/srv/bmepilots/backups")
    for path in expired_backups(root, days, dt.datetime.now(dt.timezone.utc)):
        # Candidate names are parsed timestamps and must remain direct children.
        if path.resolve().parent != root.resolve():
            raise ValueError("Backup path escaped the backup directory")
        shutil.rmtree(path)
        print(f"Expired completed local backup removed: {path.name}")


if __name__ == "__main__":
    main()
