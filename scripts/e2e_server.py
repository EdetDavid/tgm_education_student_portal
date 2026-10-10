"""Start an isolated local API for the browser tests, without touching db.sqlite3."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix='student-portal-e2e-') as temp_dir:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
        os.environ['DJANGO_SQLITE_PATH'] = str(Path(temp_dir) / 'test.sqlite3')
        os.environ['DJANGO_DEBUG'] = 'true'
        os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = os.environ.get('E2E_FRONTEND_ORIGIN', 'http://127.0.0.1:5174')
        # Empty values override .env so browser tests NEVER select the local PostgreSQL database.
        os.environ['POSTGRES_URL'] = ''
        os.environ['DATABASE_URL'] = ''
        os.environ['PGDATABASE'] = ''
        import django
        django.setup()
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from django.db import connections
        call_command('migrate', verbosity=0)
        call_command('seed_demo')
        get_user_model().objects.create_user(username='e2e-admin', password='E2eOnly934!', is_staff=True)
        get_user_model().objects.create_superuser(username='e2e-super-admin', password='E2eOnly934!')
        try:
            call_command('runserver', '127.0.0.1:8001', use_reloader=False)
        finally:
            connections.close_all()


if __name__ == '__main__':
    main()
