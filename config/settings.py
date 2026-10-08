import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)


# Keep production secrets in environment variables; the fallback is for local development.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'local-development-key-change-before-deploy',
)
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
DATABASE_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

if not DEBUG and (
    not os.environ.get('DJANGO_SECRET_KEY')
    or not DATABASE_URL
):
    raise ImproperlyConfigured(
        'Production requires DJANGO_SECRET_KEY and POSTGRES_URL (or DATABASE_URL); '
        'SQLite is development-only.'
    )

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    'localhost,127.0.0.1',
).split(',')


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'portal',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'portal.middleware.PrivateApiMiddleware',
]

ROOT_URLCONF = 'config.urls'
PORTAL_ORGANISATION_CODE = os.getenv('PORTAL_ORGANISATION_CODE', '')
SUPER_ADMIN_ACCESS_CODE = os.getenv('SUPER_ADMIN_ACCESS_CODE', '')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Use PostgreSQL when configured; otherwise use SQLite for local development.
if os.environ.get('PGDATABASE') and not DATABASE_URL:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['PGDATABASE'],
            'HOST': os.environ.get('PGHOST', 'localhost'),
            'PORT': os.environ.get('PGPORT', '5433'),
            'USER': os.environ.get('PGUSER', 'postgres'),
            'PASSWORD': os.environ.get('PGPASSWORD', ''),
            'CONN_MAX_AGE': 60,
            'CONN_HEALTH_CHECKS': True,
            'DISABLE_SERVER_SIDE_CURSORS': True,
            'OPTIONS': {'sslmode': 'prefer' if DEBUG else 'require'},
            'TEST': {'NAME': os.environ.get('PGTEST_DATABASE')},
        },
    }
elif DATABASE_URL:
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0 if os.environ.get('VERCEL') else 600,
            ssl_require=not DEBUG,
        ),
    }
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    # An omitted URL port must not inherit local PGPORT=5433 via libpq.
    DATABASES['default']['PORT'] = DATABASES['default'].get('PORT') or 5432
    DATABASES['default']['OPTIONS']['connect_timeout'] = 10
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get(
                'DJANGO_SQLITE_PATH',
                BASE_DIR / 'db.sqlite3',
            ),
            'OPTIONS': {'timeout': 20},
        },
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
        'OPTIONS': {'min_length': 12},
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Cross-origin and CSRF settings
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('DJANGO_CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    (
        'http://localhost:5173,http://127.0.0.1:5173'
        if DEBUG
        else ''
    ),
).split(',')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in CSRF_TRUSTED_ORIGINS
    if origin.strip()
]
CSRF_FAILURE_VIEW = 'portal.views.csrf_failure'


# Secure cookies and HTTP headers outside local development.
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = os.environ.get(
    'DJANGO_SSL_REDIRECT',
    str(not DEBUG),
).lower() == 'true'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

LOGIN_REDIRECT_URL = '/api/'
LOGOUT_REDIRECT_URL = '/api/'


# Django REST framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}
