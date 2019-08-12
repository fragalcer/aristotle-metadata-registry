from celery import shared_task, Task
from celery.utils.log import get_task_logger
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils.module_loading import import_string
from io import StringIO
from typing import Optional, List, Tuple
import datetime

from aristotle_mdr.utils.download import get_download_class
from aristotle_mdr.models import _concept, RegistrationAuthority
from aristotle_bg_workers.utils import lookup_model

import reversion

logger = get_task_logger(__name__)


def run_django_command(cmd, *args, **kwargs):
    err = StringIO()
    out = StringIO()
    call_command(cmd, stdout=out, stderr=err, **kwargs)
    err.seek(0)
    out.seek(0)
    message = 'Result:\n\n{out}\n\n{err}'.format(
        err=str(err.read()) or "None",
        out=str(out.read())
    )
    logger.debug(message)
    return message


class AristotleTask(Task):
    def update_state(self, task_id=None, state=None, meta=None):
        if task_id is None:
            task_id = self.request.id
        self.backend.store_result(task_id, meta, state=state, request=self.request)


@shared_task(base=AristotleTask, bind=True, name='long__reindex')
def reindex_task(self, *args, **kwargs):
    meta = {"requester": kwargs['requester'], "start_date": datetime.datetime.now()}
    self.update_state(meta=meta, state="STARTED")
    meta.update({"result": run_django_command('update_index', interactive=False)})
    return meta


@shared_task(base=AristotleTask, bind=True, name='long__recache_visibility')
def recache_visibility(self, *args, **kwargs):
    meta = {"requester": kwargs['requester'], "start_date": datetime.datetime.now()}
    self.update_state(meta=meta, state="STARTED")
    meta.update({"result": run_django_command('recache_registration_authority_item_visibility', interactive=False)})
    return meta


@shared_task(base=AristotleTask, bind=True, name='long__load_help')
def loadhelp_task(self, *args, **kwargs):
    meta = {"requester": kwargs['requester'], "start_date": datetime.datetime.now()}
    self.update_state(meta=meta, state="STARTED")
    meta.update({"result": run_django_command('load_aristotle_help')})
    return meta


@shared_task(name='fire_async_signal')
def fire_async_signal(namespace, signal_name, message={}):
    """Runs the given function with the message as argument"""
    import_string("%s.%s" % (namespace, signal_name))(message)


@shared_task(name='update_search_index')
def update_search_index(sender, instance, **kwargs):
    """Task to update the search index when a model has been saved"""
    # Fetch sender model
    sender = lookup_model(sender)
    # Fetch instance (this will raise an exception and fail the task if not found)
    instance = lookup_model(instance).objects.get(pk=instance['pk'])

    # Pass to haystack signal processor
    processor = apps.get_app_config('haystack').signal_processor
    processor.handle_save(sender, instance, **kwargs)


@shared_task(name='delete_search_index')
def delete_search_index(sender, instance, **kwargs):
    """Task to update the search index when a model has been deleted"""
    # Fetch sender model
    sender = lookup_model(sender)
    # Fetch instance (this will raise an exception and fail the task if not found)
    instance = lookup_model(instance).objects.get(pk=instance['pk'])

    # Pass to haystack signal processor
    processor = apps.get_app_config('haystack').signal_processor
    processor.handle_delete(sender, instance, **kwargs)


@shared_task(name='download')
def download(download_type: str, item_ids: List[int], user_id: int, options={}) -> Optional[str]:
    dl_class = get_download_class(download_type)

    if dl_class is not None:
        # Instantiate downloader class
        downloader = dl_class(item_ids, user_id, options)
        # Get file url
        return downloader.download()

    raise LookupError('Requested Downloader class could not be found')


@shared_task(name='send_sandbox_notification_emails')
def send_sandbox_notification_emails(name_of_user, emails_list, sandbox_access_url):
    from django.core.mail import send_mail
    from django.conf import settings

    if settings.ARISTOTLE_EMAIL_SANDBOX_NOTIFICATIONS:
        from_email = settings.ARISTOTLE_EMAIL_SANDBOX_NOTIFICATIONS
    else:
        from_email = settings.DEFAULT_FROM_EMAIL

    # Send a separate email to each email address:
    for email in emails_list:
        send_mail(
            'Sandbox Access',
            "Hello there, to access {}'s Sandbox please use the following URL: ".format(name_of_user.capitalize())
            + sandbox_access_url,
            from_email,
            [email]
        )


@shared_task(name='send_notification_email')
def send_notification_email(recipient, message):
    from django.core.mail import send_mail
    from django.conf import settings

    if settings.ARISTOTLE_EMAIL_NOTIFICATIONS:
        from_email = settings.ARISTOTLE_EMAIL_NOTIFICATIONS
    else:
        from_email = settings.DEFAULT_FROM_EMAIL

    send_mail(
        'Notification',
        message,
        from_email,
        [recipient]
    )


@shared_task(name='register_items')
def register_items(ids: List[int], cascade: bool, state: int, ra_id: int, user_id: int,
                   change_details: str, effective_date: Tuple[int, int, int], set_message: bool = True):

    # Get objects from serialized representation
    ra = RegistrationAuthority.objects.get(id=ra_id)
    items = _concept.objects.filter(id__in=ids)
    user = get_user_model().objects.get(id=user_id)
    registration_date = datetime.date(effective_date[0], effective_date[1], effective_date[2])

    # Bulk get subclasses
    items = items.select_subclasses()

    # Determine register method to use
    if cascade:
        register_method = ra.cascaded_register
    else:
        register_method = ra.register

    # To track results
    success: List = []
    failed: List = []

    # Register items
    with reversion.revisions.create_revision():
        for item in items:
            status = register_method(
                item,
                state,
                user,
                changeDetails=change_details,
                effective_date=registration_date
            )
            success.extend(status['success'])
            failed.extend(status['failed'])

        # Set reversion user
        reversion.revisions.set_user(user)

        # Set reversion message
        if set_message:
            if failed:
                bad_items = [str(i.id) for i in failed]
                message = '{num_success} items registered \n{num_failed} items failed, they had ids: {bad_ids}'.format(
                    num_success=items.count(),
                    num_failed=len(failed),
                    bad_ids=','.join(bad_items)
                )
            else:
                message = '{num_items} items registered'.format(
                    num_items=items.count()
                )

            reversion.revisions.set_comment(message)
