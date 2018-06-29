"""
Base settings necessary for running an Aristotle Instance in "the cloud (tm)"
"""

from aristotle_mdr.required_settings import *

INSTALLED_APPS = [
    "aristotle_dse",
    "comet",
    "mallard_qr",
] + list(INSTALLED_APPS)

ALLOWED_HOSTS = ["*"]
DEBUG = False
ARISTOTLE_SETTINGS['SITE_NAME'] = 'Aristotle Development Server'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_DIR = os.path.join(BASE_DIR, 'static')
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MIDDLEWARE = ['whitenoise.middleware.WhiteNoiseMiddleware'] + MIDDLEWARE

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