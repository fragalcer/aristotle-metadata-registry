import aristotle_mdr.models as models
import datetime
import ast
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from aristotle_mdr.tests import utils
from aristotle_mdr.contrib.issues.models import Issue
from aristotle_bg_workers.tasks import send_notification_email
from django.core import mail
from django.conf import settings
import logging
logger = logging.getLogger(__name__)


class TestNotifications(utils.AristotleTestUtils, TestCase):
    defaults = {}

    def setUp(self):
        super().setUp()

        self.item1 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",
            definition="my definition",
            workgroup=self.wg1,
        )
        self.item2 = models.ObjectClass.objects.create(
            name="Test Item 2 (NOT visible to tested viewers)",
            definition="my definition",
            workgroup=self.wg2,
        )
        self.item3 = models.ObjectClass.objects.create(
            name="Test Item 3 (visible to tested viewers)",
            definition="my definition",
            workgroup=self.wg1,
        )

    def test_subscriber_is_notified_of_discussion(self):
        self.assertEqual(self.wg1.discussions.all().count(), 0)
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')

        self.assertEqual(user1.notifications.count(), 0)
        models.DiscussionPost.objects.create(
            title="Hello",
            body="Sam",
            author=self.viewer,
            workgroup=self.wg1
        )
        self.assertEqual(self.wg1.discussions.all().count(), 1)
        self.assertEqual(user1.notifications.count(), 0)

        self.wg1.giveRoleToUser('viewer', user1)

        models.DiscussionPost.objects.create(
            title="Hello",
            body="Again",
            author=self.viewer,
            workgroup=self.wg1
        )

        self.assertEqual(self.wg1.discussions.all().count(), 2)
        self.assertTrue('(discussion) has been created' in user1.notifications.first().verb)
        # THE FOLLOWING TEST IS NO LONGER APPLICABLE:
        # self.assertTrue(self.viewer == user1.notifications.first().actor)
        self.assertEqual(user1.notifications.count(), 1)

    def test_subscriber_is_notified_of_comment(self):
        self.assertEqual(self.wg1.discussions.all().count(), 0)
        kenobi = get_user_model().objects.create_user('kenodi@jedi.order', '')
        grievous = get_user_model().objects.create_user('gen.grevious@separatist.mil', '')
        self.wg1.giveRoleToUser('viewer', kenobi)
        self.wg1.giveRoleToUser('viewer', grievous)

        self.assertEqual(kenobi.notifications.count(), 0)
        self.assertEqual(grievous.notifications.count(), 0)
        surprise = models.DiscussionPost.objects.create(
            title="Hello",
            body="There",
            author=kenobi,
            workgroup=self.wg1
        )
        self.assertEqual(kenobi.notifications.count(), 0)
        self.assertEqual(grievous.notifications.count(), 1)

        models.DiscussionComment.objects.create(
            body="General kenobi!!",
            author=grievous,
            post=surprise,
        )

        self.assertEqual(kenobi.notifications.count(), 1)
        self.assertEqual(grievous.notifications.count(), 1)

    def test_subscriber_is_notified_of_supersede(self):
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')
        self.wg1.giveRoleToUser('viewer', user1)
        self.favourite_item(user1, self.item1)
        self.assertTrue(user1 in self.item1.favourited_by.all())

        self.assertEqual(user1.notifications.all().count(), 0)
        self.assertTrue(self.item1.can_view(user1))
        self.assertTrue(self.item3.can_view(user1))

        models.SupersedeRelationship.objects.create(
            older_item=self.item1,
            newer_item=self.item3,
            registration_authority=self.ra
        )
        self.assertTrue(self.item3 in self.item1.superseded_by_items.visible(user1))

        user1 = get_user_model().objects.get(pk=user1.pk)
        self.assertEqual(user1.notifications.all().count(), 2)
        self.assertTrue('has been superseded in the workgroup' in user1.notifications.first().verb)
        self.assertTrue('(favourite item) has been superseded in the workgroup' in user1.notifications.last().verb)

    def test_subscriber_is_not_notified_of_supersedes_on_invisible_items(self):
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')
        self.wg1.giveRoleToUser('viewer', user1)
        self.favourite_item(user1, self.item1)
        self.assertTrue(user1 in self.item1.favourited_by.all())

        self.assertEqual(user1.notifications.all().count(), 0)
        self.assertTrue(self.item1.can_view(user1))
        self.assertFalse(self.item2.can_view(user1))

        models.SupersedeRelationship.objects.create(
            older_item=self.item1,
            newer_item=self.item2,
            registration_authority=self.ra
        )

        self.assertFalse(self.item2 in self.item1.superseded_by_items.visible(user1))

        user1 = get_user_model().objects.get(pk=user1.pk)
        self.assertEqual(user1.notifications.all().count(), 0)

    def test_registrar_is_notified_of_supersede(self):
        models.Status.objects.create(
            concept=self.item1,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2015,4,28),
            state=self.ra.locked_state
            )
        models.Status.objects.create(
            concept=self.item2,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2015,4,28),
            state=self.ra.locked_state
        )
        user1 = self.registrar
        user1.notifications.all().delete()

        self.assertEqual(user1.notifications.all().count(), 0)
        models.SupersedeRelationship.objects.create(
            older_item=self.item1,
            newer_item=self.item2,
            registration_authority=self.ra
        )

        self.assertTrue(self.item2 in self.item1.superseded_by_items.visible(user1))
        self.assertEqual(user1.notifications.all().count(), 1)
        self.assertTrue('(item registered by ' + self.ra.name + ') has been superseded.' in user1.notifications.first().verb)

    def test_registrar_is_notified_of_status_change(self):
        user1 = self.registrar
        user1.notifications.all().delete()

        self.assertEqual(user1.notifications.all().count(), 0)

        models.Status.objects.create(
            concept=self.item1,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=self.ra.locked_state
        )

        self.assertTrue(self.item1.statuses.count() == 1)
        self.assertEqual(user1.notifications.all().count(), 1)
        self.assertTrue("has been registered by Test RA with the status 'Candidate'." in user1.notifications.first().verb)

        models.Status.objects.create(
            concept=self.item1,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=self.ra.public_state
        )

        self.assertEqual(user1.notifications.all().count(), 2)
        self.assertTrue('(item registered by ' + self.ra.name + ") has changed its status to " in user1.notifications.first().verb)

    def test_subscriber_is_not_notified_when_issue_is_created_by_himself(self):

        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')

        self.wg1.giveRoleToUser('viewer', user1)

        Issue.objects.create(
            name="My huge issue",
            description="This issue is very important!",
            item=self.item1,
            submitter=user1,
            isopen=True
        )

        self.assertEqual(user1.notifications.count(), 0)

    def test_subscriber_is_notified_when_issue_is_created(self):
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')
        user2 = get_user_model().objects.create_user('subscriber2@example.com', 'subscriber2')

        self.wg1.giveRoleToUser('viewer', user1)
        self.wg1.giveRoleToUser('viewer', user2)

        Issue.objects.create(
            name="My huge issue",
            description="This issue is very important!",
            item=self.item1,
            submitter=user1,
            isopen=True
        )

        self.assertEqual(user2.notifications.count(), 1)

    def test_subscriber_is_notified_when_issue_is_created_on_favourite_item(self):
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')

        self.favourite_item(user1, self.item1)

        self.item1.name = "This is a new name"

        self.item1.save()

        self.assertEqual(user1.notifications.count(), 1)

    def test_subscriber_is_not_notified_when_the_checkbox_in_notification_permission_settings_is_not_checked(self):
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')
        # data = json.loads(user1.profile.notificationPermissions)
        # data["notification methods"]["within aristotle"] = False
        user1.profile.notificationPermissions["notification methods"]["within aristotle"] = False
        user1.profile.save()
        self.favourite_item(user1, self.item1)

        self.item1.name = "This is a new name"
        self.item1.save()

        self.assertEqual(user1.notifications.count(), 0)

    def test_subscriber_is_notified_by_email(self):
        user1 = get_user_model().objects.create_user('subscriber@example.com', 'subscriber')
        user1.profile.notificationPermissions["notification methods"]["email"] = True
        user1.profile.save()

        send_notification_email(user1.email, "hello world")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to[0], user1.email)
        self.assertEqual(mail.outbox[0].subject, 'Notification')
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].body, 'hello world')


