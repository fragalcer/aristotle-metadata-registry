from django.test import TestCase, tag, Client
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.conf import settings

import aristotle_mdr.tests.utils as utils
from aristotle_mdr import models
import datetime
import json
import os

from aristotle_mdr.utils import setup_aristotle_test_environment


setup_aristotle_test_environment()


class UserHomePages(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()

    def check_generic_pages(self):
        response = self.client.get(reverse('aristotle:userHome',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userEdit',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userInbox',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userInbox', args=['all']))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userWorkgroups',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:user_workgroups_archives',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userRecentItems',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userSandbox',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userRoles',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle_reviews:userMyReviewRequests',))
        self.assertEqual(response.status_code, 200)

    def create_content_and_share(self, user, emails):
        # Create sandbox content with editor
        models.ObjectClass.objects.create(
            name='Sandpit',
            definition='A pit containing on or more grains of sand',
            submitter=user
        )
        models.ObjectClass.objects.create(
            name='Sandbox',
            definition='A box or box like object containing an amount of sandlike substances',
            submitter=user
        )

        # Create share link with editor
        share = models.SandboxShare.objects.create(
            profile=user.profile,
            emails=json.dumps(emails)
        )

        return share

    @tag('sandbox')
    def test_user_can_view_sandbox(self):
        self.login_viewer()
        self.item1 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",definition="my definition",submitter=self.viewer)
        self.item2 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",definition="my definition")
        response = self.client.get(reverse('aristotle:userSandbox',))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.item1.concept in response.context['page'])
        self.assertTrue(self.item2.concept not in response.context['page'])

    @tag('sandbox')
    def test_user_cannot_view_registered_published_in_sandbox(self):
        self.login_viewer()
        self.item1 = models._concept.objects.create(
            name="Test Item 1 (visible to tested viewers in sandbox)",
            definition="my definition",
            submitter=self.viewer)
        # Should not see item2 because it has a review request
        self.item2 = models._concept.objects.create(
            name="Test Item 2 (not visible in sandbox, review request)",
            definition="my definition",
            submitter=self.viewer)

        self.make_review_request(self.item2, self.registrar)

        # Should not see item3 because it has a status
        self.item3 = models._concept.objects.create(
            name="Test Item 3 (not visible in sandbox, status)",
            definition="my definition",
            submitter=self.viewer
        )

        models.Status.objects.create(
            concept=self.item3,
            registrationAuthority=self.ra,
            registrationDate = datetime.date(2009,4,28),
            state =  models.STATES.standard
        )

        response = self.client.get(reverse('aristotle:userSandbox',))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.item1.concept in response.context['page'])
        self.assertTrue(self.item2.concept not in response.context['page'])
        self.assertTrue(self.item3.concept not in response.context['page'])

    @tag('sandbox')
    def test_user_can_delete_from_sandbox_ajax(self):
        self.login_viewer()
        self.item1 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",
            definition="my definition",
            submitter=self.viewer
        )

        response = self.client.post(reverse('aristotle_mdr:sandbox_delete'), {'item': self.item1.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(models.ObjectClass.objects.filter(id=self.item1.id).exists())
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict['completed'], True)
        self.assertFalse(models.ObjectClass.objects.filter(id=self.item1.id).exists())

    @tag('sandbox')
    def test_user_can_delete_from_sandbox_fallback(self):
        self.login_viewer()
        self.item1 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",
            definition="my definition",
            submitter=self.viewer
        )

        get_response = self.client.get(reverse('aristotle_mdr:sandbox_delete'))
        self.assertTemplateUsed(get_response, 'aristotle_mdr/actions/delete_sandbox.html')

        post_response = self.client.post(reverse('aristotle_mdr:sandbox_delete'), {'item': self.item1.id})
        self.assertRedirects(post_response, reverse('aristotle_mdr:userSandbox'))
        self.assertFalse(models.ObjectClass.objects.filter(id=self.item1.id).exists())

    @tag('sandbox')
    def test_delete_item_with_workgroup_sandbox(self):

        # This will test the custom field validation on the DeleteSandboxForm

        self.login_viewer()
        self.item1 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",
            definition="my definition",
            submitter=self.viewer,
            workgroup=self.wg1
        )

        post_response = self.client.post(reverse('aristotle_mdr:sandbox_delete'), {'item': self.item1.id}, follow=True)
        self.assertTrue('item' in post_response.context['form'].errors)

    @tag('sandbox')
    def test_delete_non_owned_content_sandbox(self):
        self.login_viewer()
        self.item1 = models.ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",definition="my definition",submitter=self.su)

        response = self.client.post(reverse('aristotle_mdr:sandbox_delete'), {'item': self.item1.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict['completed'], False)
        self.assertTrue('message' in response_dict.keys())


    @tag('sandbox')
    def test_delete_non_existant_content_sandbox(self):
        self.login_viewer()

        response = self.client.post(reverse('aristotle_mdr:sandbox_delete'), {'item': 123456789}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict['completed'], False)
        self.assertTrue('message' in response_dict.keys())

    @tag('share_link')
    def test_create_share_link(self):
        self.login_viewer()

        data = {
            'emails-0': 'firstone@example.com',
            'emails-1': 'nextone@example.com'
        }

        response = self.reverse_post('aristotle_mdr:userSandbox', data, status_code=200, follow=True)

        self.assertTrue(hasattr(self.viewer.profile, 'share'))
        share = self.viewer.profile.share
        emails = json.loads(share.emails)

        self.assertEqual(emails, ['firstone@example.com', 'nextone@example.com'])
        self.assertContains(response, share.uuid)

    @tag('share_link')
    def test_create_share_link_form_initial(self):
        self.login_viewer()
        emails = ['firstone@example.com', 'nextone@example.com']

        models.SandboxShare.objects.create(
            profile=self.viewer.profile,
            emails=json.dumps(emails)
        )

        response = self.reverse_get('aristotle_mdr:userSandbox')
        form = response.context['form']
        self.assertEqual(form.initial['emails'], emails)

    @tag('share_link')
    def test_create_share_link_error_display(self):
        self.login_viewer()

        data = {
            'emails-0': 'avalidemail@example.com',
            'emails-1': 'anin,validemail@example.com',
            'emails-2': 'anotherbademail@example'
        }
        response = self.reverse_post(
            'aristotle_mdr:userSandbox',
            data,
            status_code=200,
        )

        self.assertTrue('form' in response.context)
        form = response.context['form']

        self.assertTrue('emails' in form.errors)
        email_errors = form.errors['emails']

        self.assertTrue(len(email_errors), 2)
        self.assertTrue('anin,validemail@example.com is not a valid email address')
        self.assertTrue('anotherbademail@example is not a valid email address')

    @tag('share_link')
    def test_view_sandbox_correct_email(self):
        share = self.create_content_and_share(self.editor, ['vicky@example.com'])

        # View share link as viewer
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr:sharedSandbox',
            reverse_args=[share.uuid],
            status_code=200
        )

        self.assertContext(response, 'share_user', self.editor)
        self.assertContext(response, 'share_uuid', share.uuid)
        self.assertContext(response, 'user', self.viewer)

    @tag('share_link')
    def test_create_link_no_emails(self):
        self.login_viewer()
        data = {}

        response = self.reverse_post(
            'aristotle_mdr:userSandbox',
            data,
            status_code=200,
            follow=True
        )

        form = response.context['form']
        self.assertEqual(len(form.errors), 0)

        self.assertTrue(hasattr(self.viewer.profile, 'share'))
        share = self.viewer.profile.share
        emails = json.loads(share.emails)
        self.assertEqual(emails, [])

    @tag('share_link')
    def test_view_sandbox_incorrect_email(self):
        share = self.create_content_and_share(
            self.editor,
            ['steve@example.com', 'bob@example.com']
        )

        # Attempt to view share link as viewer
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr:sharedSandbox',
            reverse_args=[share.uuid],
            status_code=404
        )

    @tag('share_link')
    def test_view_sandbox_item_correct_email(self):
        share = self.create_content_and_share(
            self.editor,
            ['vicky@example.com', 'alice@example.com']
        )

        # Get sandbox item
        item = models.ObjectClass.objects.get(name='Sandpit', submitter=self.editor)

        # Attempt to view shared item
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr:sharedSandboxItem',
            reverse_args=[share.uuid, item.id],
            status_code=200
        )

        # Check for message
        self.assertContains(response, 'You are viewing a shared item')

        # Check action bar was not rendered
        self.assertTemplateNotUsed('aristotle_mdr/concepts/actionbar.html')

        self.assertInContext(response, 'breadcrumbs')

    @tag('share_link')
    def test_view_sanbox_item_incorrect_email(self):
        share = self.create_content_and_share(
            self.editor,
            ['tester@example.com', 'alice@example.com']
        )

        # Get sandbox item
        item = models.ObjectClass.objects.get(name='Sandpit', submitter=self.editor)

        # Attempt to view shared item
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr:sharedSandboxItem',
            reverse_args=[share.uuid, item.id],
            status_code=404
        )

    @tag('share_link')
    def test_view_incorrect_sandbox_item(self):
        share = self.create_content_and_share(
            self.editor,
            ['vicky@example.com', 'alice@example.com']
        )

        # Create item as viewer
        item = models.ObjectClass.objects.create(
            name='Bad object',
            definition='Bad',
            submitter=self.su
        )

        # Attempt to view shared item
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr:sharedSandboxItem',
            reverse_args=[share.uuid, item.id],
            status_code=403
        )

    @tag('share_link')
    def test_link_display_on_shared_item_page(self):
        share = self.create_content_and_share(
            self.editor,
            ['vicky@example.com', 'alice@example.com']
        )

        sandbox = models.ObjectClass.objects.get(name='Sandbox', submitter=self.editor)

        # Create a property that isn't in editors sandbox
        prop = models.Property.objects.create(
            name='Sandiness',
            definition='Sandiness',
            submitter=self.su
        )

        # Create a dec in the sandbox linking to another item in sanbox and an
        # external item
        dec = models.DataElementConcept.objects.create(
            name='Sandbox-Sandiness',
            definition='Sandbox Sandiness',
            submitter=self.editor,
            objectClass=sandbox,
            property=prop
        )

        # View shared dec item
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr:sharedSandboxItem',
            reverse_args=[share.uuid, dec.id],
            status_code=200
        )

        # Check that correct links are displayed
        self.assertContains(response, reverse('aristotle_mdr:sharedSandboxItem', args=[share.uuid, sandbox.id]))
        self.assertNotContains(response, reverse('aristotle_mdr:item', args=[sandbox.id]))

        self.assertContains(response, reverse('aristotle_mdr:item', args=[prop.id]))
        self.assertNotContains(response, reverse('aristotle_mdr:sharedSandboxItem', args=[share.uuid, prop.id]))

    def test_user_can_edit_own_details(self):
        self.login_viewer()
        new_email = 'my_new@email.com'
        response = self.client.post(reverse('aristotle:userEdit'),
            {
                'short_name':self.viewer.short_name,
                'full_name':self.viewer.full_name,
                'email': new_email,
            })
        self.assertEqual(response.status_code,302)
        self.viewer = get_user_model().objects.get(pk=self.viewer.pk)
        self.assertEqual(self.viewer.email,new_email)

    def test_viewer_can_access_homepages(self):
        self.login_viewer()
        self.check_generic_pages()

        # A viewer, has no registrar permissions:
        response = self.client.get(reverse('aristotle_reviews:userReadyForReview',))
        self.assertEqual(response.status_code,403)

        # A view is not a superuser
        response = self.client.get(reverse('aristotle:userAdminTools',))
        self.assertEqual(response.status_code,403)
        response = self.client.get(reverse('aristotle:userAdminStats',))
        self.assertEqual(response.status_code,403)
        self.logout()


    def test_user_can_filter_and_sort_workgroups(self):
        self.login_viewer()

        # make some workgroups
        for i in range(1,4):
            wg1 = models.Workgroup.objects.create(name="Test WG match_this_name %s"%i)
            wg1.giveRoleToUser('viewer',self.viewer)
            for j in range(i):
                models.ObjectClass.objects.create(name="Test item",workgroup=wg1)
        for i in range(4,7):
            wg1 = models.Workgroup.objects.create(name="Test WG %s"%i,definition="match_this_definition")
            wg1.giveRoleToUser('viewer',self.viewer)
            for j in range(i):
                models.ObjectClass.objects.create(name="Test item",workgroup=wg1)

        #should have 7 workgroups now.

        response = self.client.get(reverse('aristotle:userWorkgroups'))
        self.assertEqual(response.status_code,200)

        self.assertTrue(self.viewer.profile.myWorkgroups,7)

        wg1.archived=True

        self.assertTrue(self.viewer.profile.myWorkgroups,6)

        response = self.client.get(reverse('aristotle:userWorkgroups'))

        self.assertTrue(len(response.context['page']),self.viewer.profile.myWorkgroups.count())

        response = self.client.get(reverse('aristotle:userWorkgroups')+"?filter=match_this_name")
        self.assertEqual(len(response.context['page']),3)
        for wg in response.context['page']:
            self.assertTrue('match_this_name' in wg.name)

        response = self.client.get(reverse('aristotle:userWorkgroups')+"?sort=items_desc")
        wgs = list(response.context['page'])
        # When sorting by number off items assert that each workgroup has more items than the next.
        for a,b in zip(wgs[:-1],wgs[1:]):
            self.assertTrue(a.items.count() >= b.items.count())


    def test_user_can_filter_and_sort_archived_workgroups(self):
        self.login_viewer()

        # make some workgroups
        for i in range(1,4):
            wg1 = models.Workgroup.objects.create(name="Test WG match_this_name %s"%i)
            wg1.giveRoleToUser('viewer',self.viewer)
            for j in range(i):
                models.ObjectClass.objects.create(name="Test item",workgroup=wg1)
        for i in range(4,7):
            wg1 = models.Workgroup.objects.create(name="Test WG %s"%i,definition="match_this_definition")
            wg1.giveRoleToUser('viewer',self.viewer)
            for j in range(i):
                models.ObjectClass.objects.create(name="Test item",workgroup=wg1)
            wg1.archived=True
            wg1.save()

        #should have 7 workgroups now with 3 archived

        response = self.client.get(reverse('aristotle:user_workgroups_archives'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['page']),3)
        for wg in response.context['page']:
            self.assertTrue(wg.archived)

    def test_registrar_can_access_tools(self):
        self.login_registrar()
        self.check_generic_pages()

        self.assertTrue(self.registrar.profile.is_registrar)
        response = self.client.get(reverse('aristotle:userRegistrarTools',))
        self.assertEqual(response.status_code,200)
        response = self.client.get(reverse('aristotle_reviews:userReadyForReview',))
        self.assertEqual(response.status_code,200)

    def test_superuser_can_access_tools(self):
        self.login_superuser()
        self.check_generic_pages()

        self.assertTrue(self.su.profile.is_registrar)
        response = self.client.get(reverse('aristotle:userRegistrarTools',))
        self.assertEqual(response.status_code,200)
        response = self.client.get(reverse('aristotle_reviews:userReadyForReview',))
        self.assertEqual(response.status_code,200)

        self.assertTrue(self.su.is_superuser)
        response = self.client.get(reverse('aristotle:userAdminTools',))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:userAdminStats',))
        self.assertEqual(response.status_code, 200)
        self.logout()

    def test_login_redirects(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)

        self.login_superuser()
        response = self.client.get("/login")
        self.assertRedirects(response, reverse('aristotle:userHome'))


class UserDashRecentItems(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()
        import haystack
        haystack.connections.reload('default')

    def tearDown(self):
        call_command('clear_index', interactive=False, verbosity=0)

    def test_user_recent_dashboard_panel(self):

        self.login_editor()

        response = self.client.get(reverse('aristotle:userHome',))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recentdata']), 0)

        wizard_url = reverse('aristotle:createItem', args=['aristotle_mdr', 'objectclass'])
        wizard_form_name = "dynamic_aristotle_wizard"

        step_1_data = {
            wizard_form_name + '-current_step': 'initial',
            'initial-name': "Test Item"
        }

        response = self.client.post(wizard_url, step_1_data)
        self.assertFalse(models._concept.objects.filter(name="Test Item").exists())
        step_2_data = {
            wizard_form_name + '-current_step': 'results',
            'results-name': "Test Item",
            'results-definition': "Test Definition",
            'results-workgroup': self.wg1.pk
        }
        step_2_data.update(self.get_formset_postdata([], 'slots'))
        response = self.client.post(wizard_url, step_2_data)
        self.assertTrue(models._concept.objects.filter(name="Test Item").exists())
        self.assertEqual(models._concept.objects.filter(name="Test Item").count(), 1)
        item = models._concept.objects.filter(name="Test Item").first()

        from reversion.models import Revision

        response = self.client.get(reverse('aristotle:userHome'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context['recentdata']),
            Revision.objects.filter(user=self.editor).count()
        )

        # Lets update an item so there is some recent history
        updated_item = utils.model_to_dict_with_change_time(item)
        updated_name = updated_item['name'] + " updated!"
        updated_item['name'] = updated_name
        response = self.client.post(reverse('aristotle:edit_item', args=[item.id]), updated_item)
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('aristotle:userHome',))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recentdata']), Revision.objects.filter(user=self.editor).count())

        self.assertContains(response, "Changed name")


@tag('userprofile')
class UserProfileTests(TestCase):

    def setUp(self):

        self.newuser = get_user_model().objects.create_user(
            email='newuser@example.com',
            password='verysecure',
            short_name='new',
            full_name='new user'
        )
        self.client = Client()
        self.basedir = os.path.dirname(os.path.dirname(__file__))

    def login_newuser(self):
        self.client.logout()
        response = self.client.post(reverse('friendly_login'), {'username': 'newuser@example.com', 'password': 'verysecure'})
        self.assertEqual(response.status_code, 302)
        return response

    def post_with_profile_picture(self, formdata, code=302):

        path_to_pic = os.path.join(self.basedir, 'fixtures/aristotle.png')

        with open(path_to_pic, mode='br') as fp:
            formdata.update({'profile_picture': fp})
            response = self.client.post(reverse('aristotle_mdr:userEdit'), formdata)
            self.assertEqual(response.status_code, code)

        return response

    def get_initial(self):
        response = self.client.get(reverse('aristotle_mdr:userEdit'))
        self.assertEqual(response.status_code, 200)

        # Get initial form data
        initial = response.context['form'].initial
        return initial

    def test_load_profile(self):

        self.login_newuser()
        response = self.client.get(reverse('aristotle_mdr:userProfile'))
        self.assertEqual(response.status_code, 200)

    def test_load_profile_content(self):
        self.login_newuser()
        response = self.client.get(reverse('aristotle_mdr:userProfile'))

        # check dynamic picture loaded
        dynamic_picture_url = reverse('aristotle_mdr:dynamic_profile_picture', args=[self.newuser.id])
        self.assertContains(response, dynamic_picture_url)

        # check sessions context
        self.assertEqual(len(response.context['sessions']), 1)

    def test_load_edit_page(self):

        self.login_newuser()
        response = self.client.get(reverse('aristotle_mdr:userEdit'))
        self.assertEqual(response.status_code, 200)

        # Check initial is set properly
        initial = response.context['form'].initial
        self.assertEqual(initial['email'], 'newuser@example.com')
        self.assertEqual(initial['short_name'], 'new')
        self.assertEqual(initial['full_name'], 'new user')
        self.assertFalse('profilePicture' in initial)

    def test_profile_upload(self):

        self.login_newuser()

        initial = self.get_initial()
        response = self.post_with_profile_picture(initial)

        user = get_user_model().objects.get(email='newuser@example.com')

        self.assertTrue(user.profile.profilePicture)
        self.assertTrue(user.profile.profilePicture.name.startswith('aristotle'))
        self.assertEqual(user.profile.profilePictureWidth, 256)
        self.assertTrue(user.profile.profilePictureHeight)

    def test_profile_upload_with_clear(self):

        self.login_newuser()

        initial = self.get_initial()

        initial.update({'profile_picture-clear': 'on'})

        response = self.client.post(reverse('aristotle_mdr:userEdit'), initial)

    def test_save_without_changes(self):

        self.login_newuser()

        initial = self.get_initial()
        response = self.post_with_profile_picture(initial)

        # Post form again, with no changes
        complete_initial = self.get_initial()
        response = self.client.post(reverse('aristotle_mdr:userEdit'), complete_initial)
        self.assertEqual(response.status_code, 302)

    def test_default_profile_picture(self):

        # check page load
        response = self.client.get(reverse('aristotle_mdr:dynamic_profile_picture', args=[3]))
        self.assertEqual(response.status_code, 200)

        three_toga_color = response.context['toga_color']
        three_headshot_color = response.context['headshot_color']

        # check diffent args returns new colors
        response = self.client.get(reverse('aristotle_mdr:dynamic_profile_picture', args=[4]))
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(three_toga_color, response.context['toga_color'])
        self.assertNotEqual(three_headshot_color, response.context['headshot_color'])

        # check second request with same args returns same colors
        response = self.client.get(reverse('aristotle_mdr:dynamic_profile_picture', args=[3]))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(three_toga_color, response.context['toga_color'])
        self.assertEqual(three_headshot_color, response.context['headshot_color'])


@tag('inactive_ra', 'newtest')
class RegistrationAuthorityPages(utils.AristotleTestUtils, TestCase):

    def test_inactive_ra_inactive_in_all_ra_list(self):

        response = self.reverse_get(
            'aristotle_mdr:all_registration_authorities',
            status_code=200
        )
        self.assertEqual(len(response.context['registrationAuthorities']), 1)
        self.assertNotContains(response, '(inactive)')

        # Deactivate ra
        self.ra.active = 1
        self.ra.save()

        # Check that removed from list
        response = self.reverse_get(
            'aristotle_mdr:all_registration_authorities',
            status_code=200
        )
        self.assertEqual(len(response.context['registrationAuthorities']), 1)
        self.assertContains(response, '(inactive)')

    def test_hidden_ra_not_in_all_ra_list(self):

        # Set ra to hidden
        self.ra.active = 2
        self.ra.save()

        response = self.reverse_get(
            'aristotle_mdr:all_registration_authorities',
            status_code=200
        )
        self.assertEqual(len(response.context['registrationAuthorities']), 0)

    def test_ra_shows_as_inactive_in_registrartools(self):

        self.login_ramanager()

        # Deactivate ra
        self.ra.active = 1
        self.ra.save()

        response = self.reverse_get(
            'aristotle_mdr:userRegistrarTools',
            status_code=200
        )
        self.assertContains(response, 'Test RA')
        self.assertContains(response, '(inactive)')

    def test_hidden_ra_not_in_registrar_tools(self):

        self.login_ramanager()

        # Set ra to hidden
        self.ra.active = 2
        self.ra.save()

        response = self.reverse_get(
            'aristotle_mdr:userRegistrarTools',
            status_code=200
        )
        self.assertNotContains(response, 'Test RA')

    def test_active_in_ra_edit_form(self):

        self.login_superuser()
        response = self.client.get(reverse('aristotle_mdr:registrationauthority_edit', args=[self.ra.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('active' in response.context['form'].fields)
