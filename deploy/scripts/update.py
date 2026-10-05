#!/usr/bin/env python3
"""Root-managed deployment of verified main images; never downloads executable code."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

DEPLOY = Path(__file__).resolve().parent.parent
SERVICES = ("backend", "frontend")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def run(args, *, capture=False, timeout=900, env=None):
    return subprocess.run(args, cwd=DEPLOY, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          timeout=timeout, env=env).stdout


def compose(*args, capture=False, timeout=900):
    return run(["bash", "scripts/compose.sh", *args], capture=capture, timeout=timeout)


def atomic_write(path, value):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    temp.chmod(0o600)
    temp.replace(path)


def write_json(path, value):
    atomic_write(path, json.dumps(value, indent=2) + "\n")


def github(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "bmepilots-deployer",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = DEPLOY / "secrets/github_read_token"
    if token.is_file():
        headers["Authorization"] = "Bearer " + token.read_text().strip()
    req = urllib.request.Request("https://api.github.com/" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def select_run(runs, repository, now, settle_seconds):
    eligible = [item for item in runs if item.get("head_branch") == "main"
                and item.get("event") == "push" and item.get("status") == "completed"
                and item.get("conclusion") == "success"
                and item.get("head_repository", {}).get("full_name") == repository]
    if not eligible:
        raise RuntimeError(f"No successful main workflow for {repository}")
    latest = max(eligible, key=lambda item: item["run_number"])
    if not SHA.fullmatch(latest.get("head_sha", "")):
        raise RuntimeError("Workflow returned an invalid revision")
    completed = dt.datetime.fromisoformat(latest["updated_at"].replace("Z", "+00:00"))
    if (now - completed).total_seconds() < settle_seconds:
        raise RuntimeError(f"Latest successful {repository} run is still settling; retry later")
    return latest


def candidates(config):
    result = {}
    for service in SERVICES:
        repository = config["repositories"][service]
        if repository != f"bmepilots/{service}":
            raise RuntimeError("Only the reviewed bmepilots repositories are allowed")
        data = github(f"repos/{repository}/actions/workflows/ci.yml/runs?branch=main&event=push&status=success&per_page=20")
        selected = select_run(data["workflow_runs"], repository, dt.datetime.now(dt.timezone.utc),
                              config.get("settle_seconds", 120))
        commit = selected["head_sha"]
        comparison = github(f"repos/{repository}/compare/{commit}...main")
        if comparison["status"] not in ("ahead", "identical"):
            raise RuntimeError(f"Successful {service} revision is no longer on main")
        result[service] = {"sha": commit, "tag": f"ghcr.io/{repository}:{commit}",
                           "run_url": selected["html_url"]}
    return result


def resolve_images(selected):
    for service, candidate in selected.items():
        run(["docker", "pull", "--quiet", candidate["tag"]])
        info = json.loads(run(["docker", "image", "inspect", candidate["tag"]], capture=True))[0]
        labels = info["Config"].get("Labels") or {}
        if labels.get("org.opencontainers.image.revision") != candidate["sha"]:
            raise RuntimeError(f"{service} image revision does not match verified workflow")
        prefix = f"ghcr.io/bmepilots/{service}@"
        refs = [ref for ref in info.get("RepoDigests", [])
                if ref.startswith(prefix) and DIGEST.fullmatch(ref[len(prefix):])]
        if not refs:
            raise RuntimeError(f"No immutable digest for {service}")
        candidate.update(image=refs[0], image_id=info["Id"])
        if service == "backend":
            candidate["api_contracts"] = labels.get("io.bmepilots.api.contracts", "1").split(",")
        else:
            candidate["api_requires"] = labels.get("io.bmepilots.api.requires", "1")
    validate_contracts(selected)
    return selected


def validate_contracts(selected):
    contracts = selected["backend"]["api_contracts"]
    required = selected["frontend"]["api_requires"]
    if not contracts or any(not re.fullmatch(r"[1-9][0-9]*", value) for value in [*contracts, required]):
        raise RuntimeError("Image API contract labels are invalid; refusing deployment")
    if required not in contracts:
        raise RuntimeError("Latest verified image pair is API incompatible; wait for the matching backend/frontend CI run")


def current_images():
    result = {}
    for service in SERVICES:
        container = compose("ps", "--all", "-q", service, capture=True).strip()
        if not container:
            raise RuntimeError(f"Missing existing {service}; initial deployment is a manual operation")
        info = json.loads(run(["docker", "inspect", container], capture=True))[0]
        # Preserve the exact running image even if an operator has moved its old tag.
        reference = f"bmepilots-{service}:rollback-{info['Image'].split(':')[1][:16]}"
        run(["docker", "tag", info["Image"], reference])
        result[service] = {"image": reference, "image_id": info["Image"]}
    return result


def release_text(images):
    return "".join(f"{service.upper()}_IMAGE={images[service]['image']}\n" for service in SERVICES)


def schema_fingerprint():
    sql = "SELECT installed_rank,version,type,checksum,success FROM flyway_schema_history ORDER BY installed_rank"
    output = compose("exec", "-T", "mariadb", "sh", "-c",
                     'export MYSQL_PWD="$(cat /run/secrets/db_root_password)"; '
                     'exec mariadb -uroot --batch --skip-column-names "$MARIADB_DATABASE" -e "$1"',
                     "sh", sql, capture=True)
    if not output.strip():
        raise RuntimeError("Empty Flyway history; refuse automatic migration or rollback")
    return hashlib.sha256(output.encode()).hexdigest()


def check_gateway():
    # Execute inside gateway so both private and no-port public modes use the same check.
    compose("exec", "-T", "frontend", "wget", "--quiet", "--spider", "http://127.0.0.1/login")
    output = compose("exec", "-T", "frontend", "wget", "--quiet", "-O", "-",
                     "http://127.0.0.1/api/v1/auth/csrf", capture=True)
    if not json.loads(output).get("token"):
        raise RuntimeError("Gateway CSRF endpoint returned no token")


def apply(selected, current):
    before = schema_fingerprint()
    env = dict(os.environ, BMEPILOTS_LOCK_HELD="1")
    run(["bash", "scripts/backup.sh", "--lock-held"], timeout=7200, env=env)
    previous = release_text(current)
    atomic_write(DEPLOY / "release.previous.env", previous)
    marker = {"started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "candidate": selected,
              "previous": current, "schema_before": before, "status": "in_progress"}
    # Persist the gate before touching runtime state, so interruption requires review.
    write_json(DEPLOY / "update-failure.json", marker)
    atomic_write(DEPLOY / "release.env", release_text(selected))
    try:
        compose("config", "--quiet")
        compose("up", "-d", "--pull", "never", "--wait", "--wait-timeout", "300")
        check_gateway()
    except Exception:
        marker["status"] = "failed"
        try:
            same_schema = schema_fingerprint() == before
        except Exception:
            same_schema = False
        if same_schema:
            atomic_write(DEPLOY / "release.env", previous)
            try:
                compose("up", "-d", "--pull", "never", "--wait", "--wait-timeout", "300")
                check_gateway()
                marker["status"] = "rolled_back"
            except Exception:
                marker["status"] = "rollback_failed"
        else:
            marker["status"] = "schema_changed_or_unreadable"
        write_json(DEPLOY / "update-failure.json", marker)
        raise RuntimeError(f"Rollout failed ({marker['status']}); automatic updates paused for operator review") from None
    write_json(DEPLOY / "update-state.json", {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                             "images": selected, "schema": schema_fingerprint()})
    (DEPLOY / "update-failure.json").unlink()
    print("Verified application image pair deployed successfully.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Resolve and verify candidate images without deployment")
    args = parser.parse_args()
    if os.geteuid() != 0 or DEPLOY != Path("/srv/bmepilots/db/deploy"):
        raise RuntimeError("Run with sudo from the installed VM deployment")
    run(["mountpoint", "-q", "/srv/bmepilots"])
    os.umask(0o077)
    if (DEPLOY / "update-failure.json").exists():
        raise RuntimeError("Automatic updates paused: inspect update-failure.json and journal before clearing the gate")
    import fcntl
    descriptor = os.open("/srv/bmepilots/deploy/operation.lock",
                         os.O_CREAT | os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another deployment/backup operation is running; retry on the next timer tick.")
            return
        config = json.loads((DEPLOY / "automation.json").read_text())
        reserve = config.get("minimum_free_bytes", 5 * 1024**3)
        docker_root = run(["docker", "info", "--format", "{{.DockerRootDir}}"], capture=True).strip()
        for path in ("/srv/bmepilots", docker_root):
            if shutil.disk_usage(path).free < reserve:
                raise RuntimeError("Less than configured data/Docker disk reserve; deployment skipped")
        compose("config", "--quiet")
        selected = resolve_images(candidates(config))
        if args.check:
            print(json.dumps(selected, indent=2))
            return
        current = current_images()
        if all(selected[name]["image_id"] == current[name]["image_id"] for name in SERVICES):
            print("Running images already match the latest verified main releases.")
            return
        apply(selected, current)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # urllib/subprocess errors include no credential values; never dump response bodies.
        print(f"Deployment stopped: {error}", file=sys.stderr)
        sys.exit(1)
