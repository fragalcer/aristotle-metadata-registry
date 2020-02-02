from typing import List, Dict
import attr
import datetime
import string

from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile

import aristotle_mdr.models as models
import aristotle_mdr.perms as perms
from aristotle_mdr.utils import url_slugify_concept
from celery import states
from django_celery_results.models import TaskResult

from django_tools.unittest_utils.BrowserDebug import debug_response

from aristotle_mdr.contrib.reviews.models import ReviewRequest
from aristotle_mdr.downloader import Downloader

from time import sleep, process_time
import random


def wait_for_signal_to_fire(seconds=1):
    sleep(seconds)


def model_to_dict(item):
    from django.forms import model_to_dict as mtd
    return dict((k, v) for (k, v) in mtd(item).items() if v is not None)


def get_management_forms(item, org_records=True, slots=False, identifiers=False, item_is_model=False):
    d = {}
    if slots:
        d['slots-TOTAL_FORMS'] = 0
        d['slots-INITIAL_FORMS'] = 0
        d['slots-MIN_NUM_FORMS'] = 0
        d['slots-MAX_NUM_FORMS'] = 0

    if org_records:
        d['org_records-TOTAL_FORMS'] = 0
        d['org_records-INITIAL_FORMS'] = 0
        d['org_records-MIN_NUM_FORMS'] = 0
        d['org_records-MAX_NUM_FORMS'] = 0

    if identifiers:
        d['identifiers-TOTAL_FORMS'] = 0
        d['identifiers-INITIAL_FORMS'] = 0
        d['identifiers-MIN_NUM_FORMS'] = 0
        d['identifiers-MAX_NUM_FORMS'] = 1

    if hasattr(item, 'serialize_weak_entities'):
        weak = item.serialize_weak_entities
        for entity in weak:
            d['%s-TOTAL_FORMS' % entity[0]] = 0
            d['%s-INITIAL_FORMS' % entity[0]] = 0
            d['%s-MIN_NUM_FORMS' % entity[0]] = 0
            d['%s-MAX_NUM_FORMS' % entity[0]] = 1000

    add_through_forms = False
    if not item_is_model:
        if isinstance(item, models.DataElementDerivation):
            add_through_forms = True
    else:
        if issubclass(item, models.DataElementDerivation):
            add_through_forms = True

    if add_through_forms:
        prefixes = ['derives', 'inputs']
        for pre in prefixes:
            d['%s-TOTAL_FORMS'%pre] = 0
            d['%s-INITIAL_FORMS'%pre] = 0
            d['%s-MIN_NUM_FORMS'%pre] = 0
            d['%s-MAX_NUM_FORMS'%pre] = 1000

    return d


def get_admin_management_forms(item_class):

    d = {}
    if issubclass(item_class, models.DataElementDerivation):
        prefixes = ['dedderivesthrough_set', 'dedinputsthrough_set']
        for pre in prefixes:
            d['%s-TOTAL_FORMS'%pre] = 0
            d['%s-INITIAL_FORMS'%pre] = 0
            d['%s-MIN_NUM_FORMS'%pre] = 0
            d['%s-MAX_NUM_FORMS'%pre] = 1000

    return d


def model_to_dict_with_change_time(item, fetch_time=None):
    """
    This constructs a dictionary from a model, with a last_fetched value as well
    that is needed for checking in edit forms to prevent overrides of other saves.
    """
    if fetch_time is None:
        fetch_time = timezone.now()
    d = model_to_dict(item)
    d['last_fetched'] = str(fetch_time)

    mfs = get_management_forms(item, slots=True, identifiers=True)
    d.update(mfs)

    return d


def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def get_json_from_response(response):
    return response.json()


# Since all managed objects have the same rules, these can be used to cover everything
# This isn't an actual TestCase, we'll just pretend it is
class ManagedObjectVisibility(object):
    def setUp(self):
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")
        self.ra = models.RegistrationAuthority.objects.create(
            name="Test RA",
            definition="My RA",
            public_state=models.STATES.qualified,
            locked_state=models.STATES.candidate,
            stewardship_organisation=self.steward_org_1,
        )

        self.wg = models.Workgroup.objects.create(name="Test WG", definition="My WG", stewardship_organisation=self.steward_org_1)
        #RAFIX self.wg.registrationAuthorities.add(self.ra)

    def test_object_is_public(self):
        self.assertEqual(self.item.is_public(), False)
        s = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=models.STATES.notprogressed
        )
        self.assertEqual(self.item.is_public(), False)

        s.state = self.ra.public_state
        s.save()

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_public(), True)

        s.state = self.ra.locked_state
        s.save()

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_public(), False)

    def test_object_visibility_over_time(self):
        date = datetime.date
        s1 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2000, 1, 1),
            state=models.STATES.incomplete,
            changeDetails="s1",
        )

        # Overlaps s1 (it has no end)
        s2 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2005, 1, 1),
            until_date=datetime.date(2005, 6, 29),
            state=self.ra.public_state,
            changeDetails="s2",
        )

        # Deliberately miss 2005-06-30
        # Overlaps s1 (no end)
        s3 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2005, 7, 1),
            state=self.ra.public_state,
            changeDetails="s3",
        )

        # Overlaps s1 and s3 (no end)
        s4 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2006, 1, 1),
            until_date=datetime.date(2006, 12, 30),
            state=self.ra.locked_state,
            changeDetails="s4",
        )

        # Overlaps s1 and s3 (no end), completely contanied within s4
        s5 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2006, 3, 1),
            until_date=datetime.date(2006, 7, 30),
            state=self.ra.public_state,
            changeDetails="s5",
        )

        # Overlaps s1 and s3 (no end), overlaps s4 in 2006-11
        s6 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2006, 11, 1),
            until_date=datetime.date(2008, 7, 30),
            state=self.ra.public_state,
            changeDetails="s6",
        )

        # Overlaps s1 and s3
        the_future = (timezone.now() + datetime.timedelta(days=100)).date()
        s7 = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=the_future,
            state=self.ra.locked_state,
            changeDetails="s7",
        )

        d = date(1999, 1, 1)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), False)
        self.assertEqual(list(self.item.current_statuses(when=d)), [])

        d = date(2000, 1, 1)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), False)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s1])

        d = date(2005, 1, 1)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s2])

        d = date(2005, 6, 29)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s2])

        d = date(2005, 6, 30)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), False)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s1])

        d = date(2005, 7, 1)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s3])

        d = date(2006, 2, 1)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s4])

        d = date(2006, 3, 1)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s5])

        d = date(2006, 8, 1)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s4])

        d = date(2006, 10, 31)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s4])

        d = date(2006, 11, 1)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s6])

        d = date(2008, 7, 30)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s6])

        d = date(2008, 8, 1)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s3])

        self.assertEqual(self.item.check_is_public(), True)
        self.assertEqual(self.item.check_is_locked(), True)
        self.assertEqual(list(self.item.current_statuses()), [s3])

        d = the_future - datetime.timedelta(days=1)
        self.assertEqual(self.item.check_is_public(when=d), True)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s3])

        d = the_future + datetime.timedelta(days=1)
        self.assertEqual(self.item.check_is_public(when=d), False)
        self.assertEqual(self.item.check_is_locked(when=d), True)
        self.assertEqual(list(self.item.current_statuses(when=d)), [s7])

    def test_object_is_public_after_ra_state_changes(self):
        self.assertEqual(self.item.is_public(), False)
        models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=models.STATES.candidate
        )
        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_public(), False)

        self.ra.public_state = models.STATES.candidate
        self.ra.save()

        from django.core import management  # Lets recache this workgroup
        management.call_command('recache_registration_authority_item_visibility', ra=[self.ra.pk], verbosity=0)
        wait_for_signal_to_fire(seconds=10)  # Not sure if the above in async or not

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_public(), True)

        self.ra.public_state = models.STATES.qualified
        self.ra.save()

        from django.core import management  # Lets recache this workgroup
        management.call_command('recache_registration_authority_item_visibility', ra=[self.ra.pk], verbosity=0)
        wait_for_signal_to_fire(seconds=10)  # Not sure if the above in async or not

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_public(), False)

    def test_object_is_locked(self):
        self.assertEqual(self.item.is_locked(), False)
        s = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=models.STATES.notprogressed
        )
        self.assertEqual(self.item.is_locked(), False)

        s.state = self.ra.public_state
        s.save()

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_public(), True)

        s.state = self.ra.locked_state
        s.save()

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_locked(), True)

    def test_object_is_locked_after_ra_state_changes(self):
        self.assertEqual(self.item.is_locked(), False)
        models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=models.STATES.candidate
        )
        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_locked(), True)

        self.ra.locked_state = models.STATES.standard
        self.ra.save()

        from django.core import management  # Lets recache this RA
        management.call_command('recache_registration_authority_item_visibility', ra=[self.ra.pk], verbosity=0)
        wait_for_signal_to_fire(seconds=10)  # Not sure if the above in async or not

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_locked(), False)

        self.ra.locked_state = models.STATES.candidate
        self.ra.save()

        from django.core import management  # Lets recache this RA
        management.call_command('recache_registration_authority_item_visibility', ra=[self.ra.pk], verbosity=0)
        wait_for_signal_to_fire(seconds=10)  # Not sure if the above in async or not

        self.item = models._concept.objects.get(id=self.item.id)  # Stupid cache
        self.assertEqual(self.item.is_locked(), True)

    def test_registrar_can_view(self):
        # make editor for wg1
        r1 = get_user_model().objects.create_user('reggie@example.com', 'reg')

        self.assertEqual(perms.user_can_view(r1, self.item), False)
        models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=self.ra.locked_state
        )
        self.assertEqual(perms.user_can_view(r1, self.item), False)
        # Caching issue, refresh from DB with correct permissions
        self.ra.giveRoleToUser('registrar', r1)
        r1 = get_user_model().objects.get(pk=r1.pk)

        self.assertEqual(perms.user_can_view(r1, self.item), True)

    def test_object_submitter_can_view(self):
        # make editor for wg1
        wg1 = models.Workgroup.objects.create(name="Test WG 1", stewardship_organisation=self.steward_org_1)
        e1 = get_user_model().objects.create_user('editor1@example.com', 'editor1')
        wg1.giveRoleToUser('submitter', e1)

        # make editor for wg2
        wg2 = models.Workgroup.objects.create(name="Test WG 2", stewardship_organisation=self.steward_org_1)
        e2 = get_user_model().objects.create_user('editor2@example.com', 'editor2')
        wg2.giveRoleToUser('submitter', e2)

        # ensure object is in wg1
        self.item.workgroup = wg1
        self.item.save()

        # test editor 1 can view, editor 2 cannot
        self.assertEqual(perms.user_can_view(e1, self.item), True)
        self.assertEqual(perms.user_can_view(e2, self.item), False)

        # move object to wg2
        self.item.workgroup = wg2
        self.item.save()

        # test editor 2 can view, editor 1 cannot
        self.assertEqual(perms.user_can_view(e2, self.item), True)
        self.assertEqual(perms.user_can_view(e1, self.item), False)

        s = models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=self.ra.locked_state
        )
        # Editor 2 can view. Editor 1 cannot
        self.assertEqual(perms.user_can_view(e2, self.item), True)
        self.assertEqual(perms.user_can_view(e1, self.item), False)

        # Set status to a public state
        s.state = self.ra.public_state
        s.save()
        # Both can view, neither can edit.
        self.assertEqual(perms.user_can_view(e1, self.item), True)
        self.assertEqual(perms.user_can_view(e2, self.item), True)

    def test_object_submitter_can_edit(self):
        registrar = get_user_model().objects.create_user('registrar@example.com', 'registrar')
        self.ra.registrars.add(registrar)

        # make editor for wg1
        wg1 = models.Workgroup.objects.create(name="Test WG 1", stewardship_organisation=self.steward_org_1)
        e1 = get_user_model().objects.create_user('editor1@example.com', 'editor1')
        wg1.giveRoleToUser('submitter', e1)

        # make editor for wg2
        wg2 = models.Workgroup.objects.create(name="Test WG 2", stewardship_organisation=self.steward_org_1)
        e2 = get_user_model().objects.create_user('editor2@example.com', 'editor2')
        wg2.giveRoleToUser('submitter', e2)

        # ensure object is in wg1
        self.item.workgroup = wg1
        self.item.save()

        # test editor 1 can edit, editor 2 cannot
        self.assertEqual(perms.user_can_edit(e1, self.item), True)
        self.assertEqual(perms.user_can_edit(e2, self.item), False)

        # move Object Class to wg2
        self.item.workgroup = wg2
        self.item.save()

        # test editor 2 can edit, editor 1 cannot
        self.assertEqual(perms.user_can_edit(e2, self.item), True)
        self.assertEqual(perms.user_can_edit(e1, self.item), False)

        # self.ra.register(self.item,self.ra.locked_state,registrar,timezone.now(),)
        models.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=self.ra.locked_state
        )
        # Editor 2 can no longer edit. Neither can Editor 1
        self.assertEqual(perms.user_can_edit(e2, self.item), False)
        self.assertEqual(perms.user_can_view(e1, self.item), False)


class LoggedInViewPages(object):
    """
    This helps us manage testing across different user types.
    """
    def setUp(self):
        self.steward_org_1 = models.StewardOrganisation.objects.create(
            name='Org 1',
            description="1",
        )
        
        self.wg1 = models.Workgroup.objects.create(name="Test WG 1", definition="My WG", stewardship_organisation=self.steward_org_1)  # Editor is member
        self.wg2 = models.Workgroup.objects.create(name="Test WG 2", definition="My WG", stewardship_organisation=self.steward_org_1)
        self.ra = models.RegistrationAuthority.objects.create(name="Test RA", definition="My WG", stewardship_organisation=self.steward_org_1)
        self.wg1.save()

        self.su = get_user_model().objects.create_superuser('super@example.com', 'user')
        self.manager = get_user_model().objects.create_user('mandy@example.com', 'manager')
        self.manager.is_staff=True
        self.manager.save()
        self.editor = get_user_model().objects.create_user('eddie@example.com', 'editor')
        self.editor.is_staff=True
        self.editor.save()
        self.viewer = get_user_model().objects.create_user('vicky@example.com', 'viewer')
        self.registrar = get_user_model().objects.create_user('reggie@example.com', 'registrar')
        self.ramanager = get_user_model().objects.create_user('rachael@example.com', 'ramanager')

        self.regular = get_user_model().objects.create_user('regular@example.com', 'thanks_steve')

        self.wg1.giveRoleToUser('submitter', self.editor)
        self.wg1.giveRoleToUser('manager', self.manager)
        self.wg1.giveRoleToUser('viewer', self.viewer)
        self.ra.registrars.add(self.registrar)
        self.ra.giveRoleToUser('manager', self.ramanager)

        self.editor = get_user_model().objects.get(pk=self.editor.pk)
        self.manager = get_user_model().objects.get(pk=self.manager.pk)
        self.viewer = get_user_model().objects.get(pk=self.viewer.pk)
        self.registrar = get_user_model().objects.get(pk=self.registrar.pk)
        self.ramanager = get_user_model().objects.get(pk=self.ramanager.pk)

        self.assertEqual(self.viewer.profile.editable_workgroups.count(), 0)
        self.assertEqual(self.registrar.profile.editable_workgroups.count(), 0)

        self.assertEqual(self.manager.profile.editable_workgroups.count(), 1)
        self.assertTrue(self.wg1 in self.manager.profile.editable_workgroups.all())

        self.assertEqual(self.editor.profile.editable_workgroups.count(), 1)
        self.assertTrue(self.wg1 in self.editor.profile.editable_workgroups.all())

        self.newuser = get_user_model().objects.create_user('nathan@example.com','noobie')
        self.newuser.save()
        super().setUp()

    def get_page(self, item):
        return url_slugify_concept(item)

    def logout(self):
        self.client.post(reverse('logout'), {})

    def login_superuser(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'super@example.com', 'password': 'user'})
        self.assertEqual(response.status_code, 302)
        return response

    def login_regular_user(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'regular@example.com', 'password': 'thanks_steve'})
        self.assertEqual(response.status_code, 302)
        return response

    def login_viewer(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'vicky@example.com', 'password': 'viewer'})
        self.assertEqual(response.status_code, 302)
        return response

    def login_registrar(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'reggie@example.com', 'password': 'registrar'})
        self.assertEqual(response.status_code, 302)
        return response

    def login_ramanager(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'rachael@example.com', 'password': 'ramanager'})
        self.assertEqual(response.status_code, 302)
        return response

    def login_editor(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'eddie@example.com', 'password': 'editor'})
        self.assertEqual(response.status_code, 302)
        return response

    def login_manager(self):
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'mandy@example.com', 'password': 'manager'})
        self.assertEqual(response.status_code, 302)
        return response

    def test_logins(self):
        # Failed logins return 200, not 401
        # See http://stackoverflow.com/questions/25839434/
        response = self.client.post(reverse('friendly_login'), {'username': 'super@example.com', 'password': 'the_wrong_password'})
        self.assertEqual(response.status_code, 200)
        # Success redirects to the homepage, so its 302 not 200
        response = self.client.post(reverse('friendly_login'), {'username': 'super@example.com', 'password': 'user'})
        self.assertEqual(response.status_code, 302)
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'eddie@example.com', 'password': 'editor'})
        self.assertEqual(response.status_code, 302)
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'vicky@example.com', 'password': 'viewer'})
        self.assertEqual(response.status_code, 302)
        self.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'reggie@example.com', 'password': 'registrar'})
        self.assertEqual(response.status_code, 302)
        self.logout()

    # These are lovingly lifted from django-reversion-compare
    # https://github.com/jedie/django-reversion-compare/blob/master/tests/test_utils/test_cases.py
    def assertContainsHtml(self, response, *args):
        for html in args:
            try:
                self.assertContains(response, html, html=True)
            except AssertionError as e:  # pragma: no cover
                # Needs no coverage as the test should pass to be successful
                debug_response(response, msg="%s" % e)  # from django-tools
                raise

    def assertNotContainsHtml(self, response, *args):
        for html in args:
            try:
                self.assertNotContains(response, html, html=True)
            except AssertionError as e:  # pragma: no cover
                # Needs no coverage as the test should pass to be successful
                debug_response(response, msg="%s" % e)  # from django-tools
                raise

    def assertResponseStatusCodeEqual(self, response, code):
            try:
                self.assertEqual(response.status_code, code)
            except AssertionError as e:  # pragma: no cover
                # Needs no coverage as the test should pass to be successful
                if response.context:
                    if 'adminform' in response.context:
                        print(response.context['adminform'].form.errors.as_text())
                    elif 'form' in response.context and 'errors' in response.context['form']:
                        print(response.context['form'].form.errors.as_text())
                    elif 'errors' in response.context:
                        print(response.context['errors'])
                print(e)
                raise

    def assertDelayedEqual(self, *args):
        # This is useful when testing async code.
        # If updates aren't done in 1+2+3+4= 10seconds, then there is a problem.
        self.assertEqual(*args)
        for i in range(1, 5):
            try:
                self.assertEqual(*args)
                break
            except:
                print('failed, keep trying - %s', i)
                sleep(i)  # sleep for progressively longer, just to give it a fighting chance to finish.
        self.assertEqual(*args)


class FormsetTestUtils:
    """Utilities to help create formset post data"""
    def instantiate_formset(self, formset_class, data, instance=None, initial=None):
        prefix = formset_class().prefix
        formset_data = {}
        for i, form_data in enumerate(data):
            for name, value in form_data.items():
                if instance(value, list):
                    for j, inner in enumerate(value):
                        formset_data["{}-{}-{}_{}".format(prefix, i, name, j)] = inner
                else:
                    formset_data['{}-{}-{}'.format(prefix, i, name)] = value
        formset_data['{}-TOTAL_FORMS'.format(prefix)] = len(data)
        formset_data['{}-INITIAL_FORMS'.format(prefix)] = 0

        if instance:
            return formset_class(formset_data, instance=instance, initial=initial)
        else:
            return formset_class(formset_data, initial=initial)

    def get_formset_postdata(self, datalist: List[Dict], prefix: str = 'form', initialforms: int = 0):
        """
        Get the POST data for a formset
        Arguments:
            :param datalist: List of form dictionaries to be posted
        Keyword Arguments:
            :param initialforms: number of forms initial rendered
            :param prefix: Formsets prefix
        """

        postdata = {}
        # Add data
        index = 0
        for data in datalist:
            for key in data.keys():
                postkey = '{}-{}-{}'.format(prefix, index, key)
                postdata[postkey] = data[key]
            index += 1

        # Add management form
        postdata['{}-INITIAL_FORMS'.format(prefix)] = initialforms
        postdata['{}-TOTAL_FORMS'.format(prefix)] = index
        postdata['{}-MIN_NUM_FORMS'.format(prefix)] = 0
        postdata['{}-MAX_NUM_FORMS'.format(prefix)] = 1000

        return postdata

    def post_formset(self, url: str, extra_postdata: Dict={}, **kwargs):
        postdata = self.get_formset_postdata(**kwargs)
        postdata.update(extra_postdata)
        response = self.client.post(url, postdata)
        return response


class GeneralTestUtils:
    """General test utilities to assist with common unit test functionality"""

    def _status_check(self, response, kwargs):
        if 'status_code' in kwargs:
            self.assertEqual(response.status_code, kwargs['status_code'])

    def _get_url(self, url_name, kwargs):
        if 'reverse_args' in kwargs:
            return reverse(url_name, args=kwargs['reverse_args'])
        else:
            return reverse(url_name)

    def _reverse_request(self, function, url_name, *args, **kwargs):
        url = self._get_url(url_name, kwargs)
        request_function = getattr(self.client, function)
        response = request_function(url, *args, **kwargs)
        self._status_check(response, kwargs)
        return response

    def reverse_get(self, *args, **kwargs):
        """
        Get by reverse url

        Arguments:
        url_name -- named url to reverse
        Standard client.get args

        Extra Keyword Arguments:
        reverse_args -- args list to use during reverse
        status_code -- expected status code of response
        """
        return self._reverse_request('get', *args, **kwargs)

    def reverse_post(self, *args, **kwargs):
        """
        Post by reverse url

        Arguments:
        url_name -- named url to reverse
        Standard client.post args

        Extra Keyword Arguments:
        reverse_args -- args list to use during reverse
        status_code -- expected status code of response
        """
        return self._reverse_request('post', *args, **kwargs)

    def assertContext(self, response, key, value):
        """Check that a key and value are in context"""
        context = response.context
        self.assertTrue(key in context)
        self.assertEqual(context[key], value)

    def assertInContext(self, response, key):
        """Check that a key is in context"""
        context = response.context
        self.assertTrue(key in context)


class WizardTestUtils:
    """Helper for testing django-formtools wizards"""

    def assertWizardStep(self, response, step):
        strstep = str(step)
        self.assertEqual(response.context['wizard']['steps'].current, strstep)

    def get_step_name(self, step: int, step_names: List[str]) -> str:
        if step_names:
            name = step_names[step]
        else:
            name = str(step)

        return name

    def transform_datalist(self, datalist, wizard_name, step_names=[]):
        cskey = '{}-current_step'.format(wizard_name)
        newlist = []
        step = 0
        for formdata in datalist:
            sn = self.get_step_name(step, step_names)
            newformdata = {
                cskey: sn
            }
            for key, value in formdata.items():
                prekey = '{}-{}'.format(sn, key)
                newformdata[prekey] = value
            newlist.append(newformdata)
            step += 1

        return newlist

    def post_direct_to_wizard(self, datalist, url, step_names=[]):
        """Post to wizard without modifying datalist"""

        step = 0
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        for formdata in datalist:
            self.assertWizardStep(response, self.get_step_name(step, step_names))
            response = self.client.post(url, formdata)
            if step < len(datalist) - 1:
                # If not last step
                self.assertEqual(response.status_code, 200)
                step += 1

        return response

    def post_to_wizard(self, datalist: List[Dict[str, str]],
                       url: str, wizard_name: str, step_names: List[str]=[]):
        """Add current step and prefixes to datalist before posting"""

        updated_datalist = self.transform_datalist(datalist, wizard_name, step_names)
        return self.post_direct_to_wizard(updated_datalist, url, step_names)


class TimingTestUtils:

    def start_timer(self):
        self.start = process_time()

    def end_timer(self, event: str = 'Event'):
        end = process_time()
        total = end - self.start
        print('{} took {}s'.format(event, total))


class AristotleTestUtils(LoggedInViewPages, GeneralTestUtils,
                         WizardTestUtils, FormsetTestUtils, TimingTestUtils):
    """Combination of the above 3 utils plus some aristotle specific utils"""
    OK = 200
    MOVED_PERMANENTLY = 301
    FOUND = 302
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404

    def favourite_item(self, user, item):
        from aristotle_mdr.contrib.favourites.models import Favourite, Tag
        favtag, created = Tag.objects.get_or_create(
            profile=user.profile,
            name='',
            primary=True
        )
        Favourite.objects.get_or_create(
            tag=favtag,
            item=item
        )

    def make_item_public(self, item, ra):
        s = models.Status.objects.create(
            concept=item,
            registrationAuthority=ra,
            registrationDate=timezone.now(),
            state=ra.public_state
        )
        return s

    def make_review_request(self, item, user, requester=None, check_perms=True):
        if not requester:
            requester = self.su

        if check_perms:
            self.assertFalse(perms.user_can_view(user,item))
        item.save()
        item = item.__class__.objects.get(pk=item.pk)

        review = ReviewRequest.objects.create(
            requester=requester,registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            due_date=datetime.date(2010,1,1),
            registration_date=datetime.date(2010,1,1)
        )

        review.concepts.add(item)

        if check_perms:
            self.assertTrue(perms.user_can_view(user,item))
            self.assertTrue(perms.user_can_add_status(user,item))
        return review

    def make_review_request_iterable(self, items, user=None, request_kwargs={}):
        kwargs = {
            "requester": self.su,
            "registration_authority": self.ra,
            "target_registration_state": self.ra.locked_state,
            "registration_date": datetime.date(2013,4,2)
        }
        kwargs.update(request_kwargs)

        review = ReviewRequest.objects.create(**kwargs)

        for item in items:
            review.concepts.add(item)

        return review

@attr.s
class MockManagementForm(object):
    prefix = attr.ib(default=0)
    max_forms = attr.ib(default=1000)
    min_forms = attr.ib(default=0)
    mock_form = attr.ib(default=None)
    is_ordered = attr.ib(default=False)
    initial_forms = attr.ib(init=False)
    forms = []

    def __attrs_post_init__(self):
        self.forms = []
        self.initial_forms_count = len(self.forms)

    def add_forms(self, forms=[]):
        assert type(forms) is list
        for form in forms:
            self.add_form(form)

    def add_form(self, form={}):
        assert type(form) is dict
        if self.is_ordered:
            form['ORDER'] = form.get('ORDER', len(self.forms))
        if form:
            self.forms.append(form)

    def as_dict(self):
        base = {
            '{}-INITIAL_FORMS'.format(self.prefix): self.initial_forms_count,
            '{}-TOTAL_FORMS'.format(self.prefix): len(self.forms),
            '{}-MIN_NUM_FORMS'.format(self.prefix): self.min_forms,
            '{}-MAX_NUM_FORMS'.format(self.prefix): self.max_forms
        }

        for i, form in enumerate(self.forms):
            for field, value in form.items():
                base['{}-{}-{}'.format(self.prefix, i, field)] = value

        return base


class FakeDownloader(Downloader):
    download_type = 'fake'
    file_extension = 'fak'
    label = 'FAKE'

    def create_file(self):
        return ContentFile('')


class AsyncResultMock:
    """
    This mock AsyncResult class will replace celery's AsyncResult class to facilitate ready and status features
    First attempt to ready() will send a Pending state and the second attempt will make sure it is a success
    """

    def __init__(self, task_id):
        """
        initialize the mock async result
        :param task_id: task_id for mock task
        """
        self.status = states.RECEIVED
        self.state = states.RECEIVED
        self.id = task_id
        self.result = ''

    def ready(self):
        """
        not ready in the first try and ready in the next
        returns true once the worker finishes it's task
        :return: bool
        """
        is_ready = self.status == states.SUCCESS

        self.status = states.SUCCESS
        self.state = states.SUCCESS
        return is_ready

    def successful(self):
        """
        Returns true once the worker finishes it's task successfully
        :return: bool
        """
        return self.status == states.SUCCESS

    def forget(self):
        """
        deletes itself
        :return:
        """
        del self

    def get(self):
        result = self.result
        self.forget()
        return result


def store_taskresult(status='SUCCESS'):
    iid = ''.join(random.SystemRandom().choice('abcdefghijklmnopqrstuvwxyz0123456789-') for i in range(10))
    tr = TaskResult.objects.create(
        task_id=iid,
        status=status
    )
    tr.save()
    return tr


def get_download_result(iid):
    """
    Using taskResult to manage the celery tasks
    :return:
    """
    tr = TaskResult.objects.get(id=iid)
    return AsyncResultMock(tr.task_id)
