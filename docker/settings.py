"""
Base settings necessary for running an Aristotle Instance in "the cloud (tm)"
"""

import dj_database_url
import socket
import os
from aristotle_mdr.required_settings import *

ALLOWED_HOSTS = ["*"]
DEBUG = os.environ.get('DJANGO_DEBUG', False) == "True"
ARISTOTLE_SETTINGS['SITE_NAME'] = 'Aristotle Development Server'
ARISTOTLE_SETTINGS['DOWNLOADERS'] = [
    'aristotle_mdr.contrib.aristotle_pdf.downloader.PDFDownloader'
]

STATIC_DIR = os.path.join(BASE_DIR, 'static')
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

ROOT_URLCONF = 'urls'

ARISTOTLE_SETTINGS['CONTENT_EXTENSIONS'] += [
    'aristotle_mdr_links',
    'aristotle_dse',
    'aristotle_glossary',
    'comet',
]

INSTALLED_APPS = list(INSTALLED_APPS) + [
    "aristotle_dse",
    "aristotle_glossary",
    "comet",
    "mallard_qr",
    "aristotle_mdr_graphql",
]

from aristotle_glossary.settings import CKEDITOR_CONFIGS

MIDDLEWARE.append('impersonate.middleware.ImpersonateMiddleware')

DATABASES = {'default': dj_database_url.config()}

INSTALLED_APPS.insert(0, 'impersonate')

ROOT_URLCONF = 'urls'

CACHES= {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis/0',
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack_elasticsearch.elasticsearch5.Elasticsearch5SearchEngine',
        'URL': 'http://elasticsearch:9200',
        'INDEX_NAME': 'documents',
        'INCLUDE_SPELLING': True,
        'KWARGS': {
            'http_auth': 'elastic:changeme'
        }
    }
}

CELERY_BROKER_URL = 'redis://redis/1'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TASK_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True

LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}

# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mailhog')
EMAIL_PORT = os.environ.get('EMAIL_PORT', '1025')

# Debug toolbar
DEBUG_TOOLBAR = os.environ.get('DJANGO_DEBUG_TOOLBAR', False) == "True"
if DEBUG and DEBUG_TOOLBAR:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INSTALLED_APPS += ('debug_toolbar',)
    ip = socket.gethostbyname(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + '1']

# Webpack Loading
WEBPACK_LOADER['DEFAULT']['STATS_FILE'] = os.path.join(REPO_BASE_DIR, 'assets/dist/webpack-stats.json')
WEBPACK_LOADER['DEFAULT']['CACHE'] = False

# Static deployment
if 'STORAGE_BUCKET_NAME' in os.environ:
    STATICFILES_STORAGE = 'aristotle_mdr.storage.CustomManifestStaticFilesStorage'
    AWS_STORAGE_BUCKET_NAME=os.environ['STORAGE_BUCKET_NAME']
    AWS_QUERYSTRING_AUTH=False
    AWS_DEFAULT_ACL=None
