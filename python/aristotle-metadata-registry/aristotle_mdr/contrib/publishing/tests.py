from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from django.utils.timezone import now
import datetime
from datetime import timedelta

from reversion import revisions as reversion

from aristotle_mdr.contrib.publishing import models as pub
from aristotle_mdr.forms.search import get_permission_sqs
from aristotle_mdr.models import ObjectClass, _concept
from aristotle_mdr.tests import utils
from aristotle_mdr.utils import setup_aristotle_test_environment
from aristotle_mdr import perms

from aristotle_mdr.constants import visibility_permission_choices

from django.contrib.auth.models import AnonymousUser

setup_aristotle_test_environment()


class TestPublishing(utils.LoggedInViewPages, TestCase):
    def setUp(self):
        super().setUp()
        self.submitting_user = get_user_model().objects.create_user(
            email="self@publisher.net",
            password="self-publisher")
        with reversion.create_revision():
            self.item = ObjectClass.objects.create(
                name="A published item",
                definition="test",
                submitter=self.submitting_user
            )

    def tearDown(self):
        call_command('clear_index', interactive=False, verbosity=0)

    def test_self_publish_queryset_anon(self):
        self.logout()
        response = self.client.get(self.item.get_absolute_url())
        # self.assertTrue(response.status_code == 302)

        self.item = ObjectClass.objects.get(pk=self.item.pk)
        # self.assertFalse(self.item._is_public)

        psqs = get_permission_sqs()
        psqs = psqs.auto_query('published').apply_permission_checks()

        self.assertEqual(len(psqs), 0)

        pub_record = pub.PublicationRecord.objects.create(
            content_type=ContentType.objects.get_for_model(_concept),
            object_id=self.item.pk,
            publisher=self.submitting_user,
            publication_date=timezone.now() - timedelta(days=2),
            permission=visibility_permission_choices.public
        )

        self.item = ObjectClass.objects.get(pk=self.item.pk)
        self.assertTrue(self.item.concept.publication_details.count() == 1)

        # TODO: Make the below true
        # self.assertTrue(self.item.publication_details.count() == 1)

        items = ObjectClass.objects.all().public().all()
        self.assertTrue(items.count() == 1)
        items = _concept.objects.all().public().all()
        self.assertTrue(items.count() == 1)
        oc = ObjectClass.objects.public().get(pk=self.item.pk)
        self.assertTrue(self.item.can_view(AnonymousUser()))

        response = self.client.get(self.item.get_absolute_url())
        self.assertTrue(response.status_code == 200)

        self.item = ObjectClass.objects.get(pk=self.item.pk)
        # self.assertTrue(self.item._is_public)

        psqs = get_permission_sqs()
        psqs = psqs.auto_query('published').apply_permission_checks()
        self.assertEqual(len(psqs), 1)

    # def test_submitter_can_see_hidden_self_publish(self):
    #     pub.PublicationRecord.objects.create(
    #         user=self.submitting_user,
    #         concept=self.item,
    #         visibility=pub.PublicationRecord.VISIBILITY.active
    #     )

    #     self.assertTrue(
    #         self.item.__class__.objects.all().visible(self.registrar).filter(pk=self.item.pk).exists()
    #     )