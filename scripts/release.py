"""Run an explicit production release against an ignored environment file."""

import argparse
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env.production')
    parser.add_argument('--seed-demo', action='store_true', help='Add synthetic exhibition data')
    parser.add_argument('--create-admin', action='store_true', help='Prompt for staff credentials')
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    profile = Path(args.env_file)
    if not profile.is_absolute():
        profile = backend / profile
    if not profile.is_file():
        parser.error('Create the ignored production environment file first.')
    load_dotenv(profile, override=True)
    # Vercel deliberately redacts Secret values during env pull. Management
    # commands below do not sign sessions/tokens, so a throwaway local signing
    # key is safe; never change the deployed application's secret here.
    if os.environ.get('DJANGO_SECRET_KEY') == '[SENSITIVE]':
        os.environ['DJANGO_SECRET_KEY'] = secrets.token_urlsafe(50)
        print('Using a temporary management-only signing key; deployed secret is unchanged.')
    database = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL', '')
    hostname = urlparse(database).hostname
    if not hostname or hostname in ('localhost', '127.0.0.1', '::1'):
        parser.error('A hosted PostgreSQL URL is required; local data will not be modified.')
    if os.environ.get('DJANGO_DEBUG', '').lower() != 'false':
        parser.error('Set DJANGO_DEBUG=false in the production profile.')
    if not os.environ.get('DJANGO_SECRET_KEY'):
        parser.error('Set the same DJANGO_SECRET_KEY as the Vercel project.')
    sys.path.insert(0, str(backend))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    from django.core.management import call_command

    django.setup()
    call_command('check', deploy=True, fail_level='ERROR')
    call_command('migrate', interactive=False)
    if args.seed_demo:
        call_command('seed_demo', inquiries=240)
    if args.create_admin:
        call_command('createsuperuser')
    print('Release complete. Verify the deployed API and frontend login before sharing the demo.')


if __name__ == '__main__':
    main()
