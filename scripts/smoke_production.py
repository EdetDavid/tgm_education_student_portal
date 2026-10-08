"""Verify a synthetic submission and temporary staff login, then remove test data."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env.vercel')
    parser.add_argument('--origin', default='https://tgm-student-portal-frontend.vercel.app')
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    load_dotenv(backend / args.env_file, override=True)
    db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL', '')
    if not urlparse(db_url).hostname or urlparse(db_url).hostname in ('localhost', '127.0.0.1'):
        parser.error('A hosted database profile is required.')
    if urlparse(args.origin).scheme != 'https':
        parser.error('Use the deployed HTTPS frontend origin.')
    os.environ['DJANGO_SECRET_KEY'] = secrets.token_urlsafe(50)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    sys.path.insert(0, str(backend))
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from portal.models import Inquiry, Student

    cookies = {}
    origin = args.origin.rstrip('/')

    def request(path, data=None, token=None):
        headers = {'Accept': 'application/json', 'Origin': origin}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        if token:
            headers['X-CSRFToken'] = token
        headers['Cookie'] = '; '.join(f'{name}={value}' for name, value in cookies.items())
        # Node uses the OS trust store without disabling TLS verification. This
        # also supports Windows corporate CA chains rejected by Python 3.14's
        # stricter CA-extension validation. Credentials travel via stdin only.
        script = """
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const input = JSON.parse(Buffer.concat(chunks).toString());
const response = await fetch(input.url, {headers: input.headers,
  method: input.data === null ? 'GET' : 'POST',
  body: input.data === null ? undefined : JSON.stringify(input.data),
  signal: AbortSignal.timeout(30000)});
console.log(JSON.stringify({status: response.status,
  cookies: response.headers.getSetCookie(), data: await response.json()}));
"""
        result = subprocess.run(['node', '--use-system-ca', '--input-type=module', '-e', script],
                                input=json.dumps({'url': origin + path, 'headers': headers, 'data': data}),
                                text=True, capture_output=True, check=True, timeout=40)
        response = json.loads(result.stdout)
        for cookie in response['cookies']:
            name, value = cookie.split(';', 1)[0].split('=', 1)
            cookies[name] = value
        if response['status'] >= 400:
            raise RuntimeError(f"{path} returned HTTP {response['status']}: {response['data']}")
        return response['status'], response['data']

    identifier = uuid.uuid4().hex
    email = f'deployment-{identifier}@example.com'
    password = secrets.token_urlsafe(30)
    staff = get_user_model().objects.create_user(username=f'smoke-{identifier}', password=password, is_staff=True)
    try:
        _, catalog = request('/api/courses/')
        _, events = request('/api/events/')
        course = catalog['courses'][0]
        payload = {'full_name': 'Deployment Check', 'email': email, 'phone': '+2348012345678',
                   'course_id': course['id'], 'event_id': events['events'][0]['id'],
                   'intake': course['intake_options'][0], 'destination': 'United Kingdom',
                   'student_location': 'Lagos, Nigeria', 'message': 'Temporary deployment smoke check.'}
        status, first = request('/api/inquiries/', payload)
        assert status == 201 and first['reference'].startswith('TGM-')
        status, repeat = request('/api/inquiries/', payload)
        assert status == 200 and repeat['duplicate'] and repeat['reference'] == first['reference']
        _, csrf = request('/api/admin/csrf/')
        request('/api/admin/login/', {'username': staff.username, 'password': password}, csrf['csrfToken'])
        _, me = request('/api/admin/me/')
        assert me['username'] == staff.username
        request('/api/admin/dashboard/')
        request('/api/admin/inquiries/?q=' + first['reference'])
        print('PASS: production catalog, submission, duplicate reference, CSRF login, staff session and dashboard.')
    finally:
        if cookies.get('sessionid'):
            from django.contrib.sessions.models import Session
            Session.objects.filter(session_key=cookies['sessionid']).delete()
        Inquiry.objects.filter(email=email).delete()
        Student.objects.filter(email=email).delete()
        staff.delete()
        print('Removed the temporary smoke-test account, session and inquiry; demo data is unchanged.')


if __name__ == '__main__':
    main()
