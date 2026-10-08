"""Copy the local SQLite data into an EMPTY local PostgreSQL database safely."""
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import psycopg
from dotenv import dotenv_values


BACKEND = Path(__file__).resolve().parents[1]
EXCLUDES = ['contenttypes', 'auth.permission', 'sessions']
TABLES = ['portal_student', 'portal_course', 'portal_event', 'portal_inquiry', 'auth_user', 'auth_group']


def run_manage(*args, environment):
    subprocess.run([sys.executable, str(BACKEND / 'manage.py'), *args],
                   cwd=BACKEND, env=environment, check=True)


def canonical_fixture(path):
    records = json.loads(path.read_text(encoding='utf-8'))
    # PostgreSQL may omit a zero fractional second when serializing timestamps.
    # Compare the same instants, not '.000Z' versus 'Z' formatting differences.
    for record in records:
        for field in ['created_at', 'updated_at', 'date_joined', 'last_login']:
            value = record['fields'].get(field)
            if value:
                record['fields'][field] = datetime.fromisoformat(
                    value.replace('Z', '+00:00')).isoformat(timespec='microseconds')
    return sorted(json.dumps(record, sort_keys=True) for record in records)


def main():
    values = {**dotenv_values(BACKEND / '.env'), **os.environ}
    database = values.get('PGDATABASE', 'tgm_studentportal')
    host = values.get('PGHOST', 'localhost')
    if host not in ['localhost', '127.0.0.1', '::1']:
        raise RuntimeError('This utility only migrates to local PostgreSQL hosts.')
    if database != 'tgm_studentportal':
        raise RuntimeError('This migration is scoped to the tgm_studentportal database.')
    config = {'host': host, 'port': values.get('PGPORT', '5433'),
              'user': values.get('PGUSER', 'postgres'), 'password': values.get('PGPASSWORD', ''),
              'dbname': database, 'connect_timeout': 5}
    with psycopg.connect(**config) as target:
        existing = target.execute(
            'SELECT tablename FROM pg_tables WHERE schemaname=%s', ('public',)).fetchall()
        if existing:
            raise RuntimeError('Target database is not empty. Nothing was overwritten; use a fresh target or review it manually.')

    source_path = BACKEND / 'db.sqlite3'
    if not source_path.is_file():
        raise RuntimeError('The source db.sqlite3 does not exist.')
    backups = BACKEND / 'backups'
    backups.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    identifier = f'{timestamp}-{uuid.uuid4().hex[:8]}'
    snapshot = backups / f'before-postgres-{identifier}.sqlite3'
    fixture = backups / f'postgres-transfer-{identifier}.json'
    verification = backups / f'postgres-verification-{identifier}.json'
    # SQLite's backup API creates a consistent snapshot even if the dev server is running.
    with sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(snapshot) as backup:
            source.backup(backup)
            counts = {table: backup.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in TABLES}
    source_environment = {**os.environ, 'DJANGO_DEBUG': 'true', 'POSTGRES_URL': '',
                          'PGDATABASE': '', 'DJANGO_SQLITE_PATH': str(snapshot)}
    export_args = ['dumpdata', '--natural-foreign', '--natural-primary']
    for model in EXCLUDES:
        export_args.extend(['--exclude', model])
    run_manage(*export_args, '--output', str(fixture), environment=source_environment)

    # Only the subprocess environment contains the DSN; never print credentials.
    hostname = f'[{host}]' if ':' in host else host
    dsn = (f"postgresql://{quote(config['user'], safe='')}:{quote(config['password'], safe='')}"
           f"@{hostname}:{config['port']}/{quote(database, safe='')}")
    target_environment = {**os.environ, 'DJANGO_DEBUG': 'true', 'POSTGRES_URL': dsn,
                          'PGDATABASE': database, 'PGHOST': host, 'PGPORT': str(config['port']),
                          'PGUSER': config['user'], 'PGPASSWORD': config['password']}
    run_manage('migrate', '--noinput', environment=target_environment)
    run_manage('loaddata', str(fixture), environment=target_environment)
    run_manage(*export_args, '--output', str(verification), environment=target_environment)
    if canonical_fixture(fixture) != canonical_fixture(verification):
        raise RuntimeError('Transferred records did not match. SQLite and both export files have been preserved; do not switch databases yet.')
    with psycopg.connect(**config) as target:
        target_counts = {table: target.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in TABLES}
    if counts != target_counts:
        raise RuntimeError('Row counts did not match. Do not switch databases yet.')
    print('Verified transfer to localhost PostgreSQL:', json.dumps(target_counts))
    print('All transferred fixture fields match, including staff password hashes and inquiry references.')
    print('SQLite snapshot and private transfer files:', backups)
    print('Browser sessions were intentionally not transferred; sign in again after switching.')


if __name__ == '__main__':
    main()
