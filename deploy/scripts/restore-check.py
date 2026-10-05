#!/usr/bin/env python3
"""Restore a coordinated backup into disposable, isolated containers; never replace production."""
import argparse
import fcntl
import gzip
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('/srv/bmepilots')


def run(*args, **kwargs):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{args[0]} operation failed (exit {result.returncode}); no secret output displayed.')
    return result.stdout.decode().strip()


def wait_for(check, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            check()
            return
        except (RuntimeError, OSError):
            time.sleep(2)
    raise RuntimeError('Isolated service did not become ready within the timeout.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path)
    parser.add_argument('--email', default='admin@bmepilots2026.com')
    parser.add_argument('--password-file', type=Path, default=ROOT / 'secrets/bootstrap_admin_password')
    args = parser.parse_args()
    if os.geteuid() != 0 or not DATA.is_mount():
        raise RuntimeError('Run with sudo while the data disk is mounted.')
    backup = args.backup.resolve(strict=True)
    if backup.parent != DATA / 'backups' or not re.fullmatch(r'\d{8}T\d{6}Z', backup.name):
        raise RuntimeError('Choose one timestamped backup directly under /srv/bmepilots/backups.')
    os.umask(0o077)
    with (DATA / 'deploy/operation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Validate only known members; do not let a checksum file reference outside the backup.
        checksums = dict(line.split(maxsplit=1)[::-1] for line in (backup / 'SHA256SUMS').read_text().splitlines())
        for name in ('database.sql.gz', 'files.tar.gz', 'images.json'):
            digest = hashlib.sha256()
            with (backup / name).open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != checksums.get(name):
                raise RuntimeError(f'Backup checksum failed: {name}')
        images = json.loads((backup / 'images.json').read_text())
        refs = {}
        for service in ('mariadb', 'backend', 'frontend'):
            entry = next(item for item in images if item['ContainerName'].endswith(f'-{service}-1'))
            refs[service] = run('docker', 'image', 'inspect', '--format', '{{.Id}}', entry['ID'])
        sandbox = Path(tempfile.mkdtemp(prefix='restore-check-', dir=DATA / 'deploy')).resolve()
        prefix = 'bmepilots-restore-' + secrets.token_hex(6)
        containers = []
        network_created = False
        edge_created = False
        try:
            stores = sandbox / 'files'
            stores.mkdir()
            with tarfile.open(backup / 'files.tar.gz', 'r:gz') as archive:
                for member in archive:
                    parts = Path(member.name).parts
                    if not parts or parts[0] not in ('documents', 'attachments') or '..' in parts:
                        raise RuntimeError('Unexpected backup archive path.')
                    destination = stores.joinpath(*parts)
                    if member.isdir():
                        destination.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.extractfile(member) as source, destination.open('wb') as target:
                            shutil.copyfileobj(source, target)
                    else:
                        raise RuntimeError('Links and special files are not accepted in a restore archive.')
            for directory in ('documents', 'attachments', 'logs'):
                (stores / directory).mkdir(exist_ok=True)
            for path in [stores, *stores.rglob('*')]:
                os.chown(path, 10001, 10001)
                path.chmod(0o750 if path.is_dir() else 0o640)
            password = sandbox / 'db-password'
            password.write_text(secrets.token_hex(32))
            os.chown(password, 0, 10001)
            password.chmod(0o640)
            run('docker', 'network', 'create', '--internal', prefix)
            network_created = True
            db = prefix + '-db'
            containers.append(db)
            run('docker', 'run', '-d', '--name', db, '--network', prefix, '--network-alias', 'mariadb',
                '--mount', f'type=bind,source={password},target=/run/secrets/password,readonly',
                '-e', 'MARIADB_ROOT_PASSWORD_FILE=/run/secrets/password', '-e', 'MARIADB_DATABASE=bmepilots',
                '-e', 'MARIADB_USER=restore_app', '-e', 'MARIADB_PASSWORD_FILE=/run/secrets/password', refs['mariadb'])
            wait_for(lambda: run('docker', 'exec', db, 'healthcheck.sh', '--connect', '--innodb_initialized'))
            sql_cmd = ['docker', 'exec', '-i', db, 'sh', '-c',
                       'export MYSQL_PWD="$(cat /run/secrets/password)"; exec mariadb -uroot --batch --skip-column-names']
            with gzip.open(backup / 'database.sql.gz', 'rb') as source:
                # Stream decompressed SQL; never retain the entire dump in memory or display it.
                with tempfile.TemporaryFile() as errors:
                    process = subprocess.Popen(sql_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)
                    try:
                        shutil.copyfileobj(source, process.stdin)
                    finally:
                        process.stdin.close()
                        returncode = process.wait()
                    if returncode != 0:
                        raise RuntimeError('Isolated database restore failed.')
            def query(sql):
                return run(*sql_cmd, input=('USE bmepilots; ' + sql).encode())
            total_files = 0
            tables = set(query('SHOW TABLES;').splitlines())
            for table, directory in [('document_files', 'documents'), ('mail_attachments', 'attachments'),
                                     ('document_uploads', 'documents')]:
                if table not in tables:
                    continue
                for row in query(f'SELECT storage_key,size_bytes FROM {table};').splitlines():
                    key, size = row.split('\t')
                    if not re.fullmatch(r'[0-9a-f-]{36}', key):
                        raise RuntimeError('Invalid storage key in restored database.')
                    if (stores / directory / key).stat().st_size != int(size):
                        raise RuntimeError('Restored file size does not match database metadata.')
                    total_files += 1
            backend = prefix + '-backend'
            containers.append(backend)
            run('docker', 'run', '-d', '--name', backend, '--network', prefix, '--network-alias', 'backend',
                '--memory', '1536m', '--mount', f'type=bind,source={password},target=/run/secrets/password,readonly',
                '--mount', f'type=bind,source={stores},target=/restore',
                '-e', 'DB_URL=jdbc:mariadb://mariadb:3306/bmepilots', '-e', 'DB_USER=restore_app',
                '-e', 'DB_PASSWORD_FILE=/run/secrets/password', '-e', 'SERVER_ADDRESS=0.0.0.0',
                '-e', 'COOKIE_SECURE=false', '-e', 'MAIL_ENABLED=false', '-e', 'BOOTSTRAP_ADMIN_EMAIL=',
                '-e', 'DOCUMENT_STORAGE=/restore/documents', '-e', 'MAIL_STORAGE=/restore/attachments',
                '-e', 'APP_LOG_FILE=/restore/logs/portal.log', refs['backend'])
            wait_for(lambda: run('docker', 'exec', backend, 'curl', '-fsS', 'http://127.0.0.1:8080/actuator/health'))
            gateway = prefix + '-frontend'
            containers.append(gateway)
            # Docker does not publish ports for an internal-only network. Only the gateway
            # joins this disposable edge network; the database/backend remain isolated.
            run('docker', 'network', 'create', prefix + '-edge')
            edge_created = True
            run('docker', 'run', '-d', '--name', gateway, '--network', prefix + '-edge',
                '-p', '127.0.0.1::80', refs['frontend'])
            run('docker', 'network', 'connect', prefix, gateway)
            address = run('docker', 'port', gateway, '80/tcp')
            base = 'http://' + address
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            wait_for(lambda: opener.open(base + '/login', timeout=10).close(), timeout=60)
            def request(path, data=None):
                headers = {}
                if data is not None:
                    token = json.loads(opener.open(base + '/api/v1/auth/csrf', timeout=15).read())
                    headers = {token['headerName']: token['token'], 'Content-Type': 'application/json'}
                return opener.open(urllib.request.Request(base + path,
                    data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=30).read()
            request('/api/v1/auth/login', {'email': args.email, 'password': args.password_file.read_text().strip()})
            for endpoint in ('/users/me', '/documents', '/links', '/mail/messages', '/admin/audit-log',
                             '/calendar/events?from=2026-01-01&to=2027-01-01'):
                request('/api/v1' + endpoint)
            status = json.loads(request('/api/v1/admin/mail/status'))
            if status['enabled']:
                raise RuntimeError('Gmail must remain disabled in the isolated rehearsal.')
            samples = query('SELECT post_id,id,storage_key FROM document_files LIMIT 1;').splitlines()
            for row in samples:
                post, file_id, key = row.split('\t')
                if request(f'/api/v1/documents/{post}/files/{file_id}/download') != (stores / 'documents' / key).read_bytes():
                    raise RuntimeError('Restored document download bytes differ.')
            print(f'PASS: restored SQL, Flyway startup, {total_files} referenced files, login and protected APIs; Gmail disabled.')
            print('PASS: isolated document download bytes checked.' if samples else 'NOTE: backup contains no document to download.')
        finally:
            clean = True
            for name in reversed(containers):
                result = subprocess.run(['docker', 'rm', '-f', '-v', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                clean = clean and result.returncode == 0
            if network_created:
                result = subprocess.run(['docker', 'network', 'rm', prefix], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                clean = clean and result.returncode == 0
            if edge_created:
                result = subprocess.run(['docker', 'network', 'rm', prefix + '-edge'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                clean = clean and result.returncode == 0
            if clean and sandbox.parent == DATA / 'deploy' and sandbox.name.startswith('restore-check-'):
                shutil.rmtree(sandbox)
            elif not clean:
                print(f'Cleanup needs inspection: {prefix}, {sandbox}. Production was not changed.')


if __name__ == '__main__':
    main()
