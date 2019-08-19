from django.conf import settings
from django.urls import reverse
from django.test import TestCase, tag
from django.test.utils import override_settings
from django.utils import timezone

import aristotle_mdr.models as models
import aristotle_mdr.perms as perms
import aristotle_mdr.tests.utils as utils

import datetime

from aristotle_mdr.models import STATES


class BulkActionsTest(utils.AristotleTestUtils):
    def setUp(self):
        super().setUp()

        # There would be too many tests to test every item type against every other
        # But they all have identical logic, so one test should suffice
        self.item1 = models.ObjectClass.objects.create(name="OC1", definition="OC1 definition", workgroup=self.wg1)
        self.item2 = models.ObjectClass.objects.create(name="OC2", definition="OC2 definition", workgroup=self.wg1)
        self.item3 = models.ObjectClass.objects.create(name="OC3", definition="OC3 definition", workgroup=self.wg1)
        self.item4 = models.Property.objects.create(name="Prop4", definition="Prop4 definition", workgroup=self.wg2)
        self.item5 = models.Property.objects.create(name="Prop5", definition="Prop5 definition", workgroup=None, submitter=self.editor)

        self.item6 = models.ValueDomain.objects.create(name='Test Value Domain', definition='my definition', workgroup=self.wg1)
        self.item7 = models.DataElement.objects.create(name='Test data element', definition='my definition', workgroup=self.wg1, valueDomain=self.item6)
        self.item8 = models.DataElement.objects.create(name='Test data element', definition='my definition', workgroup=self.wg1, valueDomain=self.item6)


class BulkWorkgroupActionsPage(BulkActionsTest, TestCase):

    # Util function
    def perform_state_review(self, postdata, selected_for_change):
        postdata.pop('submit_skip')
        postdata['submit_next'] = 'value'

        change_state_response = self.client.post(
            reverse('aristotle:change_state_bulk_action'),
            postdata
        )
        self.assertFalse(change_state_response.context['deselections'])

        self.assertEqual(change_state_response.status_code, 200)
        self.assertEqual(change_state_response.context['wizard']['steps'].step1, 2) # check we are now on second step

        review_response = self.client.post(
            reverse('aristotle:change_state_bulk_action'),
            {
                'review_changes-selected_list': selected_for_change,
                'change_status_bulk_action_view-current_step': 'review_changes',
            }
        )

        return review_response

    def create_review_request(self, items):
        self.login_registrar()
        # Make a RR so the registrar can change status
        self.make_review_request_iterable(items)

    def review_changes(self, items, new_state):

        reg_date = datetime.date(2014, 10, 27)
        postdata = {
            'change_state-state': new_state,
            'change_state-items': [str(a) for a in items],
            'change_state-effective_date': reg_date,
            'change_state-cascadeRegistration': 0,
            'change_state-changeDetails': "Because",
            'change_state-registrationAuthorities': [self.ra.id],
            'submit_next': 'value',  # Go to review changes page
            'change_status_bulk_action_view-current_step': 'change_state',
        }

        response = self.reverse_post(
            'aristotle:change_state_bulk_action',
            postdata,
            status_code=200
        )

        return response

    def test_bulk_add_favourite_on_permitted_items(self):
        self.login_editor()

        self.assertEqual(self.editor.profile.favourites.count(), 0)
        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.AddFavouriteForm',
                'items': [self.item1.id, self.item2.id],
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.editor.profile.favourites.count(), 2)

    def test_bulk_add_favourite_on_permitted_items_by_anonymous(self):
        self.logout()

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.AddFavouriteForm',
                'items': [self.item1.id, self.item2.id],
            }
        )
        self.assertRedirects(response, reverse('friendly_login')+"?next="+reverse('aristotle:bulk_action'))
        self.assertEqual(response.status_code, 302)

    def test_bulk_add_favourite_on_forbidden_items(self):
        self.login_editor()

        self.assertEqual(self.editor.profile.favourites.count(), 0)
        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.AddFavouriteForm',
                'items': [self.item1.id, self.item4.id],
            },
            follow=True
        )
        self.assertEqual(self.editor.profile.favourites.count(), 1)
        self.assertFalse(self.item4 in self.editor.profile.favourites.all())
        self.assertContains(response, "1 items favourited")
        self.assertEqual(len(response.redirect_chain), 1)
        self.assertEqual(response.redirect_chain[0][1], 302)

    def test_bulk_change_workgroup_for_superuser(self):
        self.new_workgroup = models.Workgroup.objects.create(name="new workgroup", stewardship_organisation=self.steward_org_1)
        self.new_workgroup.giveRoleToUser('submitter', self.editor)
        self.login_superuser()

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': [self.item1.id, self.item2.id],
                'workgroup': [self.new_workgroup.id],
                "confirmed": True
            }
        )

        self.assertTrue(self.item1.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept in self.new_workgroup.items.all())

        self.logout()
        self.login_editor()

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': [self.item1.id, self.item2.id],
                'workgroup': [self.wg1.id],
                "confirmed": True
            },
            follow=True
        )

        self.assertTrue(self.item1.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept in self.new_workgroup.items.all())

        self.assertEqual(response.status_code, 403)

    @override_settings(ARISTOTLE_SETTINGS=dict(settings.ARISTOTLE_SETTINGS, WORKGROUP_CHANGES=['submitter']))
    def test_bulk_change_workgroup_for_editor__for_some_items(self):
        self.new_workgroup = models.Workgroup.objects.create(name="new workgroup", stewardship_organisation=self.steward_org_1)
        self.new_workgroup.giveRoleToUser('submitter', self.editor)
        self.login_editor()

        self.assertTrue(self.item1.concept not in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept not in self.new_workgroup.items.all())
        self.assertTrue(self.item4.concept not in self.new_workgroup.items.all())
        response = self.client.post(

            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': [self.item1.id, self.item2.id, self.item4.id],
                'workgroup': [self.new_workgroup.id],
                "confirmed": True
            },
            follow=True
        )

        self.assertTrue(self.item1.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item4.concept not in self.new_workgroup.items.all())

        self.assertContains(
            response,
            "Some items failed, they had the id&#39;s: %(bad_ids)s" % {
                'bad_ids': ",".join(map(str,[self.item4.pk]))
            }
        )

        self.logout()
        self.login_superuser()

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': [self.item1.id, self.item2.id, self.item4.id],
                'workgroup': [self.wg1.id],
                "confirmed": True
            },
            follow=True
        )

        self.assertTrue(self.item1.concept in self.wg1.items.all())
        self.assertTrue(self.item2.concept in self.wg1.items.all())
        self.assertTrue(self.item4.concept in self.wg1.items.all())

        self.assertNotContains(response, "Some items failed, they had the id&#39;s")

    @override_settings(ARISTOTLE_SETTINGS=dict(settings.ARISTOTLE_SETTINGS, WORKGROUP_CHANGES=['submitter']))
    def test_bulk_change_workgroup_for_editor__where_no_workgroup(self):
        self.new_workgroup = models.Workgroup.objects.create(name="new workgroup", stewardship_organisation=self.steward_org_1)
        self.new_workgroup.giveRoleToUser('submitter', self.editor)
        self.login_editor()

        self.assertTrue(self.item1.concept not in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept not in self.new_workgroup.items.all())
        self.assertTrue(self.item5.concept not in self.new_workgroup.items.all())

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': [self.item1.id, self.item2.id, self.item5.id],
                'workgroup': [self.new_workgroup.id],
                "confirmed": True
            },
            follow=True
        )

        self.assertTrue(self.item1.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item5.concept in self.new_workgroup.items.all())

        self.assertNotContains(response, "Some items failed, they had the id&#39;s")

    def test_bulk_remove_favourite(self):
        self.login_editor()

        self.assertEqual(self.editor.profile.favourites.count(), 0)
        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.AddFavouriteForm',
                'items': [self.item1.id, self.item2.id],
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.editor.profile.favourites.count(), 2)

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.RemoveFavouriteForm',
                'items': [self.item1.id, self.item2.id],
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.editor.profile.favourites.count(), 0)

    # Function used for the 2 tests below
    def bulk_status_change_on_permitted_items(self, review_changes):
        self.login_registrar()
        self.create_review_request([self.item1, self.item2])

        self.assertTrue(perms.user_can_add_status(self.registrar, self.item1))
        self.assertTrue(perms.user_can_add_status(self.registrar, self.item2))
        self.assertFalse(self.item1.is_registered)
        self.assertFalse(self.item2.is_registered)

        reg_date = datetime.date(2014,10,27)
        new_state = self.ra.locked_state
        items = [self.item1.id, self.item2.id]
        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeStateForm',
                'items': items,
            }
        )

        self.assertRedirects(response, reverse('aristotle:change_state_bulk_action'))

        change_state_get_response = self.client.get(reverse('aristotle:change_state_bulk_action'))
        self.assertEqual(change_state_get_response.context['form'].initial['items'], [str(a) for a in items])

        postdata = {
            'change_state-state': new_state,
            'change_state-items': [str(a) for a in items],
            'change_state-effective_date': reg_date,
            'change_state-cascadeRegistration': 0,
            'change_state-changeDetails': "Because",
            'change_state-registrationAuthorities': [self.ra.id],
            'submit_skip': 'value',
            'change_status_bulk_action_view-current_step': 'change_state',
        }

        if review_changes:
            selected_list = [str(self.item1.id)]
            change_state_response = self.perform_state_review(postdata, selected_list)
        else:
            change_state_response = self.client.post(
                reverse('aristotle:change_state_bulk_action'),
                postdata,
            )

        self.assertEqual(change_state_response.status_code, 302)

        item2_changed = not review_changes

        self.assertTrue(self.item1.is_registered)
        self.assertEqual(self.item2.is_registered, item2_changed)

        self.assertTrue(self.item1.current_statuses().first().effective_date == reg_date)
        self.assertTrue(self.item1.current_statuses().first().state == new_state)
        self.assertTrue(self.item1.current_statuses().first().registrationAuthority == self.ra)

        if item2_changed:
            self.assertTrue(self.item2.current_statuses().first().effective_date == reg_date)
            self.assertTrue(self.item2.current_statuses().first().state == new_state)
            self.assertTrue(self.item2.current_statuses().first().registrationAuthority == self.ra)
        else:
            self.assertEqual(len(self.item2.current_statuses()), 0)

    @tag('changestatus')
    @override_settings(ALWAYS_SYNC_REGISTER=True)
    def test_bulk_status_change_on_permitted_items_direct(self):
        self.bulk_status_change_on_permitted_items(review_changes=False)

    @tag('changestatus')
    @override_settings(ALWAYS_SYNC_REGISTER=True)
    def test_bulk_status_change_on_permitted_items_with_review(self):
        self.bulk_status_change_on_permitted_items(review_changes=True)

    @tag('changestatus')
    def test_registered_lower_deselections_on_change_status(self):
        self.login_registrar()
        # Make a RR so the registrar can change status
        items = [self.item1.id, self.item2.id]
        self.create_review_request(items)

        # Register item1 as candidate
        models.Status.objects.create(
            concept=self.item1,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=STATES.candidate
        )

        # Register item2 as standard
        models.Status.objects.create(
            concept=self.item2,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=STATES.standard
        )

        self.assertTrue(perms.user_can_add_status(self.registrar, self.item1))
        self.assertTrue(perms.user_can_add_status(self.registrar, self.item2))

        response = self.review_changes(items, STATES.standard)
        self.assertTrue(response.context['deselections'])

        form = response.context['form']
        extra_info = form.fields['selected_list'].widget.extra_info
        self.assertTrue(extra_info[self.item1.id]['perm'])
        self.assertTrue(extra_info[self.item1.id]['checked'])
        self.assertTrue(extra_info[self.item2.id]['perm'])
        self.assertFalse(extra_info[self.item2.id]['checked'])

    @tag('changestatus')
    def test_registered_higher_deselections_on_change_status(self):
        self.login_registrar()
        # Make a RR so the registrar can change status
        items = [self.item1.id, self.item2.id]
        self.create_review_request(items)

        # Register item1 as candidate
        models.Status.objects.create(
            concept=self.item1,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=STATES.standard
        )

        # Register item2 as standard
        models.Status.objects.create(
            concept=self.item2,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=STATES.preferred
        )

        self.assertTrue(perms.user_can_add_status(self.registrar, self.item1))
        self.assertTrue(perms.user_can_add_status(self.registrar, self.item2))

        response = self.review_changes(items, STATES.standard)
        self.assertTrue(response.context['deselections'])

        form = response.context['form']
        extra_info = form.fields['selected_list'].widget.extra_info
        self.assertTrue(extra_info[self.item1.id]['perm'])
        self.assertFalse(extra_info[self.item1.id]['checked'])
        self.assertTrue(extra_info[self.item2.id]['perm'])
        self.assertFalse(extra_info[self.item2.id]['checked'])

    @tag('changestatus')
    def test_deslections_on_first_registration(self):
        self.login_registrar()
        # Make a RR so the registrar can change status
        items = [self.item1.id]
        self.create_review_request(items)

        self.assertTrue(perms.user_can_add_status(self.registrar, self.item1))

        response = self.review_changes(items, STATES.standard)
        self.assertFalse(response.context['deselections'])

        form = response.context['form']
        extra_info = form.fields['selected_list'].widget.extra_info
        self.assertTrue(extra_info[self.item1.id]['perm'])
        self.assertTrue(extra_info[self.item1.id]['checked'])

    @tag('changestatus')
    @override_settings(ALWAYS_SYNC_REGISTER=True)
    def test_bulk_status_change_cascade_common_child(self):
        # Test for changestatus with cascade  on 2 items with a common child
        self.login_superuser()

        items = [self.item7.id, self.item8.id]

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeStateForm',
                'items': items,
            }
        )

        self.assertRedirects(response, reverse('aristotle:change_state_bulk_action'))

        change_state_get_response = self.client.get(reverse('aristotle:change_state_bulk_action'))
        self.assertEqual(change_state_get_response.context['form'].initial['items'], [str(a) for a in items])

        items_strings = [str(a) for a in items]
        reg_date = datetime.date(2014, 10, 27)
        new_state = self.ra.locked_state

        postdata = {
            'change_state-state': new_state,
            'change_state-items': items_strings,
            'change_state-effective_date': reg_date,
            'change_state-cascadeRegistration': 1,
            'change_state-changeDetails': "Because",
            'change_state-registrationAuthorities': [self.ra.id],
            'submit_next': 'value',
            'change_status_bulk_action_view-current_step': 'change_state',
        }

        change_response = self.client.post(reverse('aristotle:change_state_bulk_action'), postdata)

        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(change_response.context['wizard']['steps'].step1, 2)  # check we are now on second step

        queryset = change_response.context['form'].fields['selected_list'].queryset
        self.assertEqual(queryset.count(), 3)  # Should not have multiples of the same item

        cascade_items = [self.item6, self.item7, self.item8]
        cascade_items_strings = [str(a.id) for a in cascade_items]

        review_response = self.client.post(
            reverse('aristotle:change_state_bulk_action'),
            {
                'review_changes-selected_list': cascade_items_strings,
                'change_status_bulk_action_view-current_step': 'review_changes',
            }
        )
        self.assertEqual(review_response.status_code, 302)

        for item in cascade_items:

            self.assertTrue(item.current_statuses().first().effective_date == reg_date)
            self.assertTrue(item.current_statuses().first().state == new_state)
            self.assertTrue(item.current_statuses().first().registrationAuthority == self.ra)

    @tag('changestatus')
    @override_settings(ALWAYS_SYNC_REGISTER=True)
    def test_bulk_status_change_on_forbidden_items(self):
        self.login_registrar()
        self.make_review_request(self.item1, self.registrar)

        self.assertTrue(perms.user_can_add_status(self.registrar, self.item1))
        self.assertFalse(perms.user_can_add_status(self.registrar, self.item4))
        self.assertFalse(self.item1.is_registered)
        self.assertFalse(self.item2.is_registered)
        self.assertFalse(self.item4.is_registered)

        reg_date = datetime.date(2014, 10, 27)
        new_state = self.ra.locked_state
        items = [self.item1.id, self.item2.id, self.item4.id]

        action_response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeStateForm',
                'items': items,
            }
        )

        self.assertRedirects(action_response, reverse('aristotle:change_state_bulk_action'))

        get_response = self.client.get(reverse('aristotle:change_state_bulk_action'))
        self.assertEqual(get_response.context['form'].initial['items'], [str(a) for a in items])

        response = self.client.post(
            reverse('aristotle:change_state_bulk_action'),
            {
                'change_state-state': new_state,
                'change_state-items': [str(a) for a in items],
                'change_state-effective_date': reg_date,
                'change_state-cascadeRegistration': 0,
                'change_state-changeDetails': "Because",
                'change_state-registrationAuthorities': [self.ra.id],
                'change_state-confirmed': 'confirmed',
                'submit_skip': 'value',
                'change_status_bulk_action_view-current_step': 'change_state',
            },
            follow=True
        )

        self.assertEqual(200, response.status_code)
        self.assertTrue(self.item1.is_registered)
        self.assertFalse(self.item2.is_registered)
        self.assertFalse(self.item4.is_registered)

        self.assertTrue(self.item1.current_statuses().first().effective_date == reg_date)
        self.assertTrue(self.item1.current_statuses().first().state == new_state)
        self.assertTrue(self.item1.current_statuses().first().registrationAuthority == self.ra)

        self.assertEqual(len(response.redirect_chain), 1)
        self.assertEqual(response.redirect_chain[0][1], 302)

    # TODO: bulk action *and* cascade, where a user doesn't have permission for child elements.

    @override_settings(ARISTOTLE_SETTINGS=dict(settings.ARISTOTLE_SETTINGS, WORKGROUP_CHANGES=['submitter']))
    def test_bulk_workgroup_change_with_all_from_workgroup_list(self):
        from aristotle_mdr.utils.cached_querysets import register_queryset

        self.new_workgroup = models.Workgroup.objects.create(name="new workgroup",
                                                             stewardship_organisation=self.steward_org_1)
        self.new_workgroup.giveRoleToUser('submitter', self.editor)
        self.login_editor()

        self.assertTrue(self.item1.concept not in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept not in self.new_workgroup.items.all())
        self.assertTrue(self.item4.concept not in self.new_workgroup.items.all())

        qs = self.wg1.items.all()

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': qs,
                'workgroup': [self.new_workgroup.id],
                "confirmed": True,
                'qs': register_queryset(qs),
                'all_in_queryset': True
            },
            follow=True
        )

        self.assertTrue(self.item1.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item2.concept in self.new_workgroup.items.all())
        self.assertTrue(self.item4.concept not in self.new_workgroup.items.all())

        self.logout()
        self.login_superuser()

        qs = self.new_workgroup.items.all()

        self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.ChangeWorkgroupForm',
                'items': [],
                'workgroup': [self.wg1.pk],
                "confirmed": True,
                'qs': register_queryset(qs),
                'all_in_queryset': True
            },
            follow=True
        )

        self.assertTrue(self.item1.concept in self.wg1.items.all())
        self.assertTrue(self.item2.concept in self.wg1.items.all())
        self.assertTrue(self.item4.concept not in self.wg1.items.all())
