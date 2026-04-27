# patient_scheduling_system/settings.py

from pathlib import Path
from datetime import timedelta
import os
import sys
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Load secret key from .env file
SECRET_KEY = config('SECRET_KEY', default='fallback-secret-key')

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_celery_results',   # ← add this
    'django_celery_beat',      # ← add this
    # Project apps
    'authentication',
    'hospital',
    'patients',
    'leads',
    'reports',
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
    'hospital.middleware.TenantMiddleware',
]

ROOT_URLCONF = 'patient_scheduling_system.urls'

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

WSGI_APPLICATION = 'patient_scheduling_system.wsgi.application'

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ─── Password Validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True
STATIC_URL    = 'static/'

# ─── Custom User Model ────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'authentication.CustomUser'

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# ─── SimpleJWT ────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
CORS_ALLOW_CREDENTIALS = True

# ─── Email ────────────────────────────────────────────────────────────────────
if 'test' in sys.argv:
    # During tests print emails to terminal — no SMTP needed
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
elif DEBUG:
    # During development print emails to terminal
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # Production — use real SMTP
    EMAIL_BACKEND     = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST        = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT        = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS     = True
    EMAIL_HOST_USER   = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

DEFAULT_FROM_EMAIL    = config('DEFAULT_FROM_EMAIL', default='noreply@hospital.com')
PASSWORD_RESET_TIMEOUT = 3600

# ─── Cache — No Redis ─────────────────────────────────────────────────────────
# Using Django's built-in local memory cache
# Works without any external service like Redis
# Data lives in memory while server is running
# Resets when server restarts — acceptable for development
CACHES = {
    'default': {
        'BACKEND':  'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pss-cache',  # unique name for this cache
    }
}

# ─── Celery Configuration ─────────────────────────────────────────────────────
# TASK_ALWAYS_EAGER = True means tasks run synchronously in the same process
# No broker, no worker, no Redis needed
# Perfect for development — task runs immediately when .delay() is called
CELERY_TASK_ALWAYS_EAGER         = True
CELERY_TASK_EAGER_PROPAGATES     = True  # propagate exceptions from tasks
CELERY_BROKER_URL                = 'memory://'  # in-memory broker
CELERY_RESULT_BACKEND            = 'cache+memory://'  # in-memory result backend
CELERY_ACCEPT_CONTENT            = ['json']
CELERY_TASK_SERIALIZER           = 'json'

try:
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'apply-lead-criteria-nightly': {
            'task':     'leads.tasks.apply_lead_criteria',
            'schedule': crontab(hour=0, minute=0),
        }
    }
except ImportError:
    pass