from urllib.parse import urlsplit


def allowed_hosts(environ):
    hosts = [host.strip() for host in environ.get(
        'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1'
    ).split(',') if host.strip()]
    # Trust only this deployment's platform-provided names, never all Vercel tenants.
    for key in ('VERCEL_URL', 'VERCEL_PROJECT_PRODUCTION_URL', 'VERCEL_BRANCH_URL'):
        value = environ.get(key, '').strip()
        if value:
            hostname = urlsplit(value if '://' in value else f'https://{value}').hostname
            if hostname and hostname not in hosts:
                hosts.append(hostname)
    return hosts
