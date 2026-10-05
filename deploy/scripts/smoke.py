"""VM-only operator check. Run with sudo; never prints credentials or cookies."""
import http.cookiejar
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / '.smoke-state.json'
BASE = os.environ.get('BMEPILOTS_SMOKE_URL', 'http://127.0.0.1:8088').rstrip('/')
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener.addheaders = [('User-Agent', 'BMEPilotsDeploymentCheck/1.0')]


def request(path, method='GET', data=None, content_type=None, expected=200):
    headers = {}
    if method != 'GET':
        token = json.loads(opener.open(BASE + '/api/v1/auth/csrf').read())
        headers[token['headerName']] = token['token']
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        content_type = 'application/json'
    if content_type:
        headers['Content-Type'] = content_type
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        response = opener.open(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    assert response.status == expected, f'{method} {path}: HTTP {response.status}, expected {expected}'
    return response.read()


mode = sys.argv[1]
assert mode in ('create', 'create-staged', 'verify'), 'Use create/create-staged before recreation, verify afterward.'
request('/login')
request('/documents')  # SPA deep-link fallback
request('/api/v1/users/me', expected=401)
settings = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
request('/api/v1/auth/login', 'POST', {
    'email': settings.get('BOOTSTRAP_ADMIN_EMAIL') or 'admin@bmepilots2026.com',
    'password': (ROOT / 'secrets/bootstrap_admin_password').read_text().strip(),
})
for path in ('/users/me', '/dashboard', '/documents', '/links', '/admin/audit-log', '/admin/mail/status',
             '/calendar/events?from=2026-01-01&to=2027-01-01'):
    request('/api/v1' + path)

payload = b'BME Pilots VM persistence verification.\n'
if mode in ('create', 'create-staged'):
    assert not STATE.exists(), 'Previous verification state exists; verify it before another run.'
    boundary = uuid.uuid4().hex
    parts = []
    if mode == 'create':
        for name, value in [('title', 'Deployment verification'), ('description', 'Temporary operator test; removed after verification.')]:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    field = 'file' if mode == 'create-staged' else 'files'
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="verification.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode() + payload + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    if mode == 'create-staged':
        upload = json.loads(request('/api/v1/documents/uploads', 'POST', b''.join(parts), f'multipart/form-data; boundary={boundary}', 201))
        post = json.loads(request('/api/v1/documents', 'POST', {
            'title': 'Deployment verification', 'description': 'Temporary operator test; removed after verification.',
            'uploadIds': [upload['id']],
        }, expected=201))
    else:
        post = json.loads(request('/api/v1/documents', 'POST', b''.join(parts), f'multipart/form-data; boundary={boundary}', 201))
    STATE.write_text(json.dumps({'postId': post['id']}))
    STATE.chmod(0o600)
    request('/api/v1/documents/' + post['id'] + '/comments', 'POST', {'body': 'Persistence check.'}, expected=201)
    print('PASS: SPA, authentication, API routes, document upload and comment creation.')
else:
    post_id = json.loads(STATE.read_text())['postId']
    detail = json.loads(request('/api/v1/documents/' + post_id))
    assert len(detail['files']) == 1 and len(detail['comments']) == 1
    download = f"/api/v1/documents/{post_id}/files/{detail['files'][0]['id']}/download"
    assert request(download) == payload
    request(f"/api/v1/documents/{post_id}?version={detail['post']['version']}", 'DELETE', expected=204)
    STATE.unlink()
    print('PASS: document bytes, metadata and comments survived container recreation; test post removed.')
request('/api/v1/auth/logout', 'POST', expected=204)
request('/api/v1/users/me', expected=401)
print('PASS: logout invalidates the session.')
