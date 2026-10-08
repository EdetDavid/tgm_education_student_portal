"""Back up and merge local Student Portal PostgreSQL records into Neon."""

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
TABLES = ['portal_course', 'portal_event', 'portal_student', 'auth_group', 'auth_user',
          'auth_user_groups', 'auth_group_permissions', 'auth_user_user_permissions', 'portal_inquiry']
KEYS = {
    'portal_course': ('name', 'level', 'location'),
    'portal_event': ('name', 'city', 'venue', 'date', 'time'),
    'portal_student': ('email',), 'auth_group': ('name',), 'auth_user': ('username',),
    'portal_inquiry': ('reference',),
}
LINKS = {'portal_inquiry': {'student_id': 'portal_student', 'course_id': 'portal_course', 'event_id': 'portal_event'}}
IGNORED = {'portal_student': {'created_at', 'updated_at'}, 'auth_user': {'date_joined', 'last_login'},
           'portal_inquiry': {'created_at'}}


def key(table, row):
    return tuple(row[field].strip().lower() if field == 'email' else row[field] for field in KEYS[table])


def fetch(connection, table):
    return connection.execute(sql.SQL('SELECT * FROM {} ORDER BY id').format(sql.Identifier(table))).fetchall()


def insert(connection, table, row):
    values = {field: value for field, value in row.items() if field != 'id'}
    if table == 'portal_course':
        from psycopg.types.json import Jsonb
        values['intakes'] = Jsonb(values['intakes'])
    return connection.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING id').format(
        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, values)),
        sql.SQL(',').join(sql.Placeholder() for _ in values)), list(values.values())).fetchone()['id']


def backup(dsn, destination, pg_dump):
    # Pass credentials via libpq environment variables, never process arguments.
    environment = dict(os.environ)
    for name in ('PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE'):
        environment.pop(name, None)
    address = urlparse(dsn)
    options = parse_qs(address.query)
    environment.update(PGHOST=address.hostname, PGPORT=str(address.port or 5432),
                       PGDATABASE=unquote(address.path.lstrip('/')),
                       PGUSER=unquote(address.username or ''),
                       PGPASSWORD=unquote(address.password or ''),
                       PGSSLMODE=options.get('sslmode', ['require'])[0],
                       PGCHANNELBINDING=options.get('channel_binding', ['require'])[0],
                       PGCONNECT_TIMEOUT='10')
    result = subprocess.run([pg_dump, '--format=custom', '--no-owner', '--file', str(destination)],
                            env=environment, capture_output=True, text=True)
    if result.returncode:
        message = result.stderr.replace(dsn, '[redacted connection]')
        if address.password:
            message = message.replace(unquote(address.password), '[redacted]')
        raise RuntimeError('Cloud backup failed before import: ' + message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--pg-dump', default='C:/Program Files/PostgreSQL/18/bin/pg_dump.exe')
    args = parser.parse_args()
    local = dotenv_values(BACKEND / '.env')
    cloud = dotenv_values(BACKEND / '.env.vercel')
    if local.get('PGDATABASE') != 'tgm_studentportal' or local.get('PGHOST') not in ('localhost', '127.0.0.1'):
        parser.error('Source must be local tgm_studentportal.')
    cloud_url = cloud.get('POSTGRES_URL_NON_POOLING') or cloud.get('DATABASE_URL_UNPOOLED') or cloud.get('POSTGRES_URL') or cloud.get('DATABASE_URL')
    if not cloud_url or not (urlparse(cloud_url).hostname or '').endswith('.neon.tech'):
        parser.error('Target must be the configured Neon database.')
    local_config = {'host': local['PGHOST'], 'port': local.get('PGPORT', '5433'),
                    'dbname': local['PGDATABASE'], 'user': local.get('PGUSER', 'postgres'),
                    'password': local.get('PGPASSWORD', ''), 'connect_timeout': 10}
    with psycopg.connect(**local_config, row_factory=dict_row) as source, psycopg.connect(
            cloud_url, connect_timeout=10, row_factory=dict_row) as target:
        source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        records = {table: fetch(source, table) for table in TABLES}
        existing = {table: fetch(target, table) for table in TABLES}
        permissions = fetch(source, 'auth_permission')
        cloud_permissions = fetch(target, 'auth_permission')
        local_ct = {r['id']: (r['app_label'], r['model']) for r in fetch(source, 'django_content_type')}
        cloud_ct = {r['id']: (r['app_label'], r['model']) for r in fetch(target, 'django_content_type')}
        permission_keys = {(cloud_ct[r['content_type_id']], r['codename']): r['id'] for r in cloud_permissions}
        permission_map = {r['id']: permission_keys[(local_ct[r['content_type_id']], r['codename'])] for r in permissions}
        mapping, pending, conflicts, matched = {}, {}, [], Counter()
        for table in KEYS:
            lookup = {key(table, row): row for row in existing[table]}
            if len(lookup) != len(existing[table]):
                raise RuntimeError(f'Ambiguous natural keys in {table}; nothing imported.')
            mapping[table], pending[table] = {}, []
            for original in records[table]:
                row = dict(original)
                for field, parent in LINKS.get(table, {}).items():
                    row[field] = mapping[parent].get(row[field], ('new', row[field]))
                found = lookup.get(key(table, row))
                if found:
                    differences = [field for field in row if field != 'id' and field not in IGNORED.get(table, set())
                                   and row[field] != found[field]]
                    if differences:
                        conflicts.append({'table': table, 'source_id': original['id'], 'fields': differences})
                    mapping[table][original['id']] = found['id']
                    matched[table] += 1
                else:
                    pending[table].append(original)
                    mapping[table][original['id']] = ('new', original['id'])
        print('Source counts:', json.dumps({table: len(rows) for table, rows in records.items()}))
        print('Cloud counts:', json.dumps({table: len(rows) for table, rows in existing.items()}))
        print('New records:', json.dumps({table: len(rows) for table, rows in pending.items()}))
        print('Conflicts:', json.dumps(conflicts))
        if conflicts:
            raise RuntimeError('Conflicting records found; no cloud data was overwritten.')
        if not args.apply:
            print('Audit only. Re-run with --apply after reviewing the plan.')
            return
        backups = BACKEND / 'backups'
        backups.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        cloud_backup = backups / f'neon-before-local-transfer-{stamp}.dump'
        backup(cloud_url, cloud_backup, args.pg_dump)
        local_snapshot = backups / f'local-neon-transfer-{stamp}.json'
        local_snapshot.write_text(json.dumps(records, default=str), encoding='utf-8')
        target.rollback()
        # Lock app/auth tables during the short merge, preventing concurrent
        # submissions from racing the preflight check. Source stays read-only.
        target.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(
            sql.SQL(',').join(map(sql.Identifier, TABLES))))
        if any(fetch(target, table) != existing[table] for table in TABLES):
            raise RuntimeError('Cloud data changed during backup; rerun the audit. Nothing imported.')
        for table in KEYS:
            for original in pending[table]:
                row = dict(original)
                for field, parent in LINKS.get(table, {}).items():
                    row[field] = mapping[parent][row[field]]
                mapping[table][original['id']] = insert(target, table, row)
        for table, foreign in {
                'auth_user_groups': {'user_id': 'auth_user', 'group_id': 'auth_group'},
                'auth_group_permissions': {'group_id': 'auth_group', 'permission_id': 'permission'},
                'auth_user_user_permissions': {'user_id': 'auth_user', 'permission_id': 'permission'}}.items():
            pairs = {tuple(r[field] for field in foreign) for r in existing[table]}
            for original in records[table]:
                row = {field: (permission_map[value] if parent == 'permission' else mapping[parent][value])
                       for field, parent in foreign.items() for value in [original[field]]}
                if tuple(row.values()) not in pairs:
                    insert(target, table, row)
                    pairs.add(tuple(row.values()))
        # Verify every local record, including hashed passwords and mapped FKs,
        # before committing. Existing cloud records are never updated/deleted.
        for table in KEYS:
            imported = {r['id']: r for r in fetch(target, table)}
            for original in records[table]:
                expected = dict(original)
                expected['id'] = mapping[table][original['id']]
                for field, parent in LINKS.get(table, {}).items():
                    expected[field] = mapping[parent][original[field]]
                ignored = IGNORED.get(table, set()) if original not in pending[table] else set()
                if any(expected[field] != imported[expected['id']][field] for field in expected if field not in ignored):
                    raise RuntimeError(f'Verification failed for {table}; transaction rolled back.')
        counts = {table: len(fetch(target, table)) for table in KEYS}
        target.commit()
        print('Verified cloud totals:', json.dumps(counts))
        print('Staff password hashes and inquiry references preserved. Existing cloud records unchanged.')
        print('Private recovery files:', cloud_backup, local_snapshot)
        print('Sessions intentionally not copied; sign in on the frontend with your existing staff credentials.')


if __name__ == '__main__':
    main()
