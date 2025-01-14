from __future__ import absolute_import, unicode_literals
from celery import Celery


# set the default Django settings module for the 'celery' program.
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aristotle_mdr.settings')

app = Celery('aristotle')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
# app.autodiscover_tasks(related_name='downloader')


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))



# from celery import signals
# @signals.setup_logging.connect
# def setup_celery_logging(**kwargs):
#     pass
# app.log.setup()

