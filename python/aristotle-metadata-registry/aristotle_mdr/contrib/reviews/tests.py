from django.urls import reverse
from django.test import TestCase, tag, override_settings
from django.core.cache import cache
from unittest import skip
from urllib.parse import urlencode
import aristotle_mdr.models as MDR
from aristotle_mdr.contrib.reviews.forms import RequestReviewCreateForm
from aristotle_mdr.contrib.reviews.models import ReviewRequest
import aristotle_mdr.tests.utils as utils
from aristotle_mdr import perms
from aristotle_mdr.contrib.reviews import models
from aristotle_mdr.contrib.reviews.const import REVIEW_STATES
from django.contrib.auth import get_user_model

import datetime

User = get_user_model()


# I wanted to call this review-R-Ls or rev-U-R-Ls.
review_urls = [
    'aristotle_reviews:review_details',
    'aristotle_reviews:review_list',
    'aristotle_reviews:request_impact',
    # 'aristotle_reviews:request_checks',
    'aristotle_reviews:request_issues',
]

review_edit_urls = [
    'aristotle_reviews:request_update',
]

review_accept_urls = [
    'aristotle_reviews:accept_review',
    'aristotle_reviews:endorse_review',
]


class ReviewRequestBulkActions(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()

        # There would be too many tests to test every item type against every other
        # But they all have identical logic, so one test should suffice
        self.item1 = MDR.ObjectClass.objects.create(name="Test Item 1 (visible to tested viewers)", definition="my definition", workgroup=self.wg1)
        self.item2 = MDR.ObjectClass.objects.create(name="Test Item 2 (NOT visible to tested viewers)", definition="my definition", workgroup=self.wg2)
        self.item3 = MDR.ObjectClass.objects.create(name="Test Item 3 (only visible to the editor)", definition="my definition", workgroup=None, submitter=self.editor)

        self.item4 = MDR.ValueDomain.objects.create(name='Test Value Domain', definition='my definition', workgroup=self.wg1)
        self.item5 = MDR.DataElement.objects.create(name='Test data element', definition='my definition', workgroup=self.wg1, valueDomain=self.item4)

        cache.clear()

    def test_bulk_review_request_on_permitted_items(self):
        self.login_viewer()

        self.assertTrue(perms.user_can_view(self.viewer, self.item1))
        self.assertFalse(perms.user_can_view(self.viewer, self.item2))

        self.assertTrue(models.ReviewRequest.objects.count() == 0)

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.contrib.reviews.forms.RequestReviewBulkActionForm',
                'items': [self.item1.id, self.item2.id],
            },
            follow=True
        )

        params = {'items': [self.item1.id]}
        url = "{}?{}".format(
            reverse("aristotle_reviews:review_create"),
            urlencode(params, True)
        )
        self.assertRedirects(response, url)

        self.assertContains(response, "items when registering metadata")
        self.assertTrue(self.item1 in response.context['form']['concepts'].initial)
        self.assertTrue(self.item2 not in response.context['form']['concepts'].initial)
        self.assertTrue(len(response.context['form']['concepts'].initial) == 1)

    def test_bulk_review_request_on_forbidden_items(self):
        self.login_viewer()

        self.assertTrue(perms.user_can_view(self.viewer, self.item1))
        self.assertTrue(perms.user_can_view(self.viewer, self.item4))

        self.assertTrue(models.ReviewRequest.objects.count() == 0)

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.contrib.reviews.forms.RequestReviewBulkActionForm',
                'items': [self.item1.id, self.item4.id],
            },
            follow=True
        )

        params = {'items': [self.item1.id, self.item4.id]}
        # This solution would work 100% of the time in django 2
        # https://code.djangoproject.com/ticket/27398
        # url = "{}?{}".format(
        #     reverse("aristotle_reviews:review_create"),
        #     urlencode(params, True)
        # )
        # self.assertRedirects(response, url)
        self.assertContains(response, "items when registering metadata")
        self.assertTrue(self.item1 in response.context['form']['concepts'].initial)
        self.assertTrue(self.item4 in response.context['form']['concepts'].initial)
        self.assertTrue(len(response.context['form']['concepts'].initial) == 2)


class ReviewRequestDetailTestCase(utils.AristotleTestUtils, TestCase):
    """Tests for viewing a review"""

    def setUp(self):
        super().setUp()
        self.item = MDR.ObjectClass.objects.create(
            name='Stuff',
            definition='Stuff'
        )
        self.item2 = MDR.ObjectClass.objects.create(
            name='Junk',
            definition='Junk'
        )

    def create_single_item_review_request(self, state):
        rr = models.ReviewRequest.objects.create(
            registration_authority=self.ra,
            requester=self.editor,
            target_registration_state=state,
        )
        rr.concepts.add(self.item)
        return rr

    def test_view_review_request(self):
        rr = self.create_single_item_review_request(MDR.STATES.standard)
        self.login_editor()
        response = self.reverse_get(
            'aristotle_reviews:review_details',
            reverse_args=[rr.id]
        )
        self.assertEqual(response.status_code, 200)

    def test_view_request_impact(self):
        rr = self.create_single_item_review_request(MDR.STATES.standard)
        self.login_editor()
        response = self.reverse_get(
            'aristotle_reviews:request_impact',
            reverse_args=[rr.id]
        )
        self.assertEqual(response.status_code, 200)

    def test_view_review_request_no_target_state(self):
        rr = self.create_single_item_review_request(None)
        self.login_editor()
        response = self.reverse_get(
            'aristotle_reviews:review_details',
            reverse_args=[rr.id]
        )
        self.assertEqual(response.status_code, 200)

    def test_view_request_impact_no_target_state(self):
        rr = self.create_single_item_review_request(None)
        self.login_editor()
        response = self.reverse_get(
            'aristotle_reviews:request_impact',
            reverse_args=[rr.id]
        )
        self.assertEqual(response.status_code, 200)

    def test_rr_validations_with_cascade(self):
        oc = MDR.ObjectClass.objects.create(
            name='Pokemon',
            definition='Pocket monster'
        )
        dec = MDR.DataElementConcept.objects.create(
            name='Pokemon - Attack',
            definition='A pokemon\'s attack'
        )
        rr = models.ReviewRequest.objects.create(
            registration_authority=self.ra,
            requester=self.editor,
            target_registration_state=MDR.STATES.standard,
            cascade_registration=1
        )
        rr.concepts.add(oc)

        self.login_editor()
        response = self.reverse_get(
            'aristotle_reviews:request_checks',
            reverse_args=[rr.id]
        )
        self.assertEqual(response.status_code, 200)

    def test_request_visible_multiple_registrars(self):
        # create 2 users
        user = get_user_model().objects.create_user(
            email='example@example.com',
            password='1234'
        )
        user2 = get_user_model().objects.create_user(
            email='example2@example.com',
            password='1234'
        )
        # create ra
        ra1 = MDR.RegistrationAuthority.objects.create(
            name='First RA',
            definition='First',
            stewardship_organisation=self.steward_org_1
        )
        # Add both user to ra as registrars
        ra1.registrars.add(user)
        ra1.registrars.add(user2)
        # Make sure user 1 is a registrar
        self.assertTrue(user.profile.is_registrar)

        # create review request by user 1
        rr1 = models.ReviewRequest.objects.create(
            registration_authority=ra1,
            requester=user,
            target_registration_state=MDR.STATES.standard,
        )

        # Check to see how many reviews user 1 can see
        visible = models.ReviewRequest.objects.visible(user)
        self.assertEqual(visible.count(), 1)


class ReviewRequestSupersedesTestCase(utils.AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.item = MDR.ObjectClass.objects.create(
            name='My Object',
            definition='mine'
        )
        # Create a review
        self.review = models.ReviewRequest.objects.create(
            registration_authority=self.ra,
            requester=self.editor,
            target_registration_state=MDR.STATES.standard,
            registration_date=datetime.date(2001, 1, 1)
        )
        self.review.concepts.add(self.item)

    def create_editor_item(self, name, definition):
        return MDR.ObjectClass.objects.create(
            name=name,
            definition=definition,
            submitter=self.editor
        )

    # Create a supersedes relation
    def create_ss_relation(self, older, newer):
        rel = MDR.SupersedeRelationship.objects.create(
            proposed=True,
            older_item=older,
            newer_item=newer,
            registration_authority=self.review.registration_authority,
            review=self.review,
        )
        return rel

    def post_formset(self, data, initialforms):
        post_data = self.get_formset_postdata(data, initialforms=initialforms)
        self.login_editor()
        response = self.reverse_post(
            'aristotle_mdr_review_requests:request_supersedes_edit',
            post_data,
            reverse_args=[self.review.pk],
        )
        return response

    def test_rr_supersedes(self):
        self.login_editor()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes_edit',
            reverse_args=[self.review.pk]
        )
        self.assertEqual(response.status_code, 200)

    def test_formest_queryset_existing_rel(self):
        # Add second item to review
        item2 = self.create_editor_item('My 2nd Object', 'mine')
        self.review.concepts.add(item2)
        # Create items to be used in supersede relation
        old1 = self.create_editor_item('Old Object', 'old')
        # Create supersedes relations
        ss = self.create_ss_relation(old1, self.item)
        # Get formset
        self.login_editor()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes_edit',
            reverse_args=[self.review.pk],
            status_code=200
        )
        # Check initial
        qs = response.context['formset'].queryset
        self.assertEqual(qs.count(), 1)
        self.assertTrue(ss in qs)

    def test_formset_data_attrs(self):
        # Add second item to review
        item2 = self.create_editor_item('My 2nd Object', 'mine')
        self.review.concepts.add(item2)
        # Get formset
        self.login_editor()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes_edit',
            reverse_args=[self.review.pk],
            status_code=200
        )
        form = response.context['formset'].empty_form
        widget_data = form.fields['newer_item'].widget.data
        self.assertTrue('data-label' in widget_data)
        self.assertCountEqual(
            widget_data['data-label'],
            {self.item.id: 'aristotle_mdr.objectclass', item2.id: 'aristotle_mdr.objectclass'}
        )

    def test_rr_supersedes_create(self):
        """Test the creation of a review re"""
        # Add second item to review
        item2 = self.create_editor_item('My 2nd Object', 'mine')
        self.review.concepts.add(item2)
        # Create items to be used in supersede relation
        old1 = self.create_editor_item('Old Object', 'old')
        old2 = self.create_editor_item('Old 2nd Object', 'old')
        # Post data
        data = [
            {'older_item': old1.id, 'newer_item': self.item.id, 'message': 'wow'},
            {'older_item': old2.id, 'newer_item': item2.id, 'message': 'nice'},
        ]
        response = self.post_formset(data, 0)
        self.assertEqual(response.status_code, 302)
        # Check objects created
        self.review.refresh_from_db()
        self.assertEqual(self.review.proposed_supersedes.count(), 2)

    def test_rr_supersedes_update(self):
        # Add second item to review
        item2 = self.create_editor_item('My 2nd Object', 'mine')
        self.review.concepts.add(item2)
        # Create items to be used in supersede relation
        old1 = self.create_editor_item('Old Object', 'old')
        old2 = self.create_editor_item('Old 2nd Object', 'old')
        old3 = self.create_editor_item('Old 3rd Object', 'old')
        old4 = self.create_editor_item('Old 4th Object', 'old')
        # Create supersedes relations
        ss1 = self.create_ss_relation(old1, self.item)
        ss2 = self.create_ss_relation(old2, item2)
        # Post data
        data = [
            {'id': ss1.id, 'older_item': old3.id, 'newer_item': self.item.id, 'message': 'wow'},
            {'id': ss2.id, 'older_item': old4.id, 'newer_item': item2.id, 'message': 'nice'},
        ]
        response = self.post_formset(data, 2)
        self.assertEqual(response.status_code, 302)
        # Check objects updated
        self.review.refresh_from_db()
        supersedes = self.review.proposed_supersedes
        self.assertEqual(supersedes.count(), 2)
        ss1.refresh_from_db()
        self.assertEqual(ss1.older_item, old3.concept)
        ss2.refresh_from_db()
        self.assertEqual(ss2.older_item, old4.concept)

    def test_rr_supersedes_delete(self):
        # Add second item to review
        item2 = self.create_editor_item('My 2nd Object', 'mine')
        self.review.concepts.add(item2)
        # Create items to be used in supersede relation
        old1 = self.create_editor_item('Old Object', 'old')
        old2 = self.create_editor_item('Old 2nd Object', 'old')
        # Create supersedes relations
        ss1 = self.create_ss_relation(old1, self.item)
        ss2 = self.create_ss_relation(old2, item2)
        # Post data
        data = [
            {'id': ss1.id, 'newer_item': self.item.id, 'message': 'wow', 'DELETE': 'on'},
            {'id': ss2.id, 'newer_item': item2.id, 'message': 'nice', 'DELETE': 'on'},
        ]
        response = self.post_formset(data, 2)
        self.assertEqual(response.status_code, 302)
        # Check objects deleted
        self.assertEqual(self.review.proposed_supersedes.count(), 0)

    def test_rr_supersedes_incompatible_types(self):
        # Add second item to review
        item2 = MDR.DataElement.objects.create(
            name='My DE',
            definition='mine',
            submitter=self.editor
        )
        self.review.concepts.add(item2)
        # Create items to be used in supersede relation (both are object
        # classes)
        old1 = self.create_editor_item('Old Object', 'old')
        old2 = self.create_editor_item('Old 2nd Object', 'old')
        # Post data
        data = [
            {'older_item': old1.id, 'newer_item': self.item.id, 'message': 'wow'},
            {'older_item': old2.id, 'newer_item': item2.id, 'message': 'nice'},
        ]
        response = self.post_formset(data, 0)
        self.assertEqual(response.status_code, 200)
        # Check no objects created
        self.review.refresh_from_db()
        self.assertEqual(self.review.proposed_supersedes.count(), 0)

    def test_rr_supersedes_not_viewable_item(self):
        # Add second item to review
        item2 = MDR.DataElement.objects.create(
            name='My DE',
            definition='mine',
            submitter=self.viewer
        )
        self.review.concepts.add(item2)
        # Create items to be used in supersede relation (both are object
        # classes)
        old1 = self.create_editor_item('Old Object', 'old')
        old2 = self.create_editor_item('Old 2nd Object', 'old')
        # Post data
        data = [
            {'older_item': old1.id, 'newer_item': self.item.id, 'message': 'wow'},
            {'older_item': old2.id, 'newer_item': item2.id, 'message': 'nice'},
        ]
        response = self.post_formset(data, 0)
        self.assertEqual(response.status_code, 200)
        # Check no objects created
        self.review.refresh_from_db()
        self.assertEqual(self.review.proposed_supersedes.count(), 0)

    def test_rr_supersedes_blank_form(self):
        """Submit a blank form along with valid data, should be ignored"""
        # Create items to be used in supersede relation
        old1 = self.create_editor_item('Old Object', 'old')
        old2 = self.create_editor_item('Old 2nd Object', 'old')
        # Post data
        data = [
            {'older_item': old1.id, 'newer_item': self.item.id, 'message': 'wow'},
            {'older_item': '', 'newer_item': '', 'message': ''},
        ]
        response = self.post_formset(data, 0)
        self.assertEqual(response.status_code, 302)
        # Check objects created
        self.review.refresh_from_db()
        self.assertEqual(self.review.proposed_supersedes.count(), 1)

    def test_newer_item_field_and_older_item_field_are_required(self):
        old1 = self.create_editor_item('Old Object', 'old')
        new1 = self.item
        empty_newer_item_data = [{'older_item': old1.id, 'newer_item': '', 'message': 'hello'}]
        empty_older_item_data = [{'older_item': '', 'newer_item': new1.id, 'message': 'hello'}]

        response = self.post_formset(empty_newer_item_data, 0)

        self.assertFalse(response.context['formset'][0].is_valid())

        response2 = self.post_formset(empty_older_item_data, 0)

        self.assertFalse(response2.context['formset'][0].is_valid())

    def test_accept_review_supersedes_approved(self):
        """ Test that accepting the review supersedes the approval """
        older = MDR.ObjectClass.objects.create(name='2nd', definition='Second')
        ss = self.create_ss_relation(older, self.item)
        self.assertEqual(self.review.proposed_supersedes.count(), 1)

        wizard_data = [
            {'status_message': 'We changing', 'close_review': '1'},
            {'selected_list': [str(self.item.id)]}
        ]

        self.login_registrar()
        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_review_requests:accept_review', args=[self.review.id]),
            'review_accept_view',
            ['review_accept', 'review_changes']
        )
        self.assertEqual(response.status_code, 302)

        self.review.refresh_from_db()
        # Check that the review was approved, and change to an 'Approved' state
        self.assertEqual(self.review.status, REVIEW_STATES.approved)
        ss.refresh_from_db()
        self.assertFalse(ss.proposed)

    @override_settings(ALWAYS_SYNC_REGISTER=True)
    def test_supersedes_status_applied(self):
        older = MDR.ObjectClass.objects.create(name='Old', definition='Very old')
        ss = self.create_ss_relation(older, self.item)
        self.assertEqual(self.review.proposed_supersedes.count(), 1)

        wizard_data = [
            {'status_message': 'We changing', 'close_review': '1'},
            {'selected_list': [str(self.item.id)]}
        ]

        self.login_registrar()
        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_review_requests:accept_review', args=[self.review.id]),
            'review_accept_view',
            ['review_accept', 'review_changes']
        )
        self.assertEqual(response.status_code, 302)

        older.refresh_from_db()
        status = older.statuses.first()
        self.assertIsNotNone(status)
        self.assertEqual(status.state, MDR.STATES.superseded)

    def test_supersedes_edit_page_registrar(self):
        """Make sure a registrar can't edit supersedes (need to be manager)"""
        self.login_registrar()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes_edit',
            reverse_args=[self.review.id]
        )
        self.assertEqual(response.status_code, 403)

    def test_supersedes_edit_page_manager(self):
        """Make sure a manager can edit supersedes"""
        self.login_ramanager()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes_edit',
            reverse_args=[self.review.id]
        )
        self.assertEqual(response.status_code, 200)

    def test_supersedes_view_page_registrar(self):
        """Make sure a registrar can view supersedes page, but has no edit button"""
        self.login_registrar()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes',
            reverse_args=[self.review.id]
        )
        self.assertEqual(response.status_code, 200)
        can_edit = response.context['can_edit_review']
        self.assertEqual(can_edit, False)

    @skip('Currently user needs to be a registrar as well as manager for this')
    def test_supersedes_view_page_manager(self):
        """Make sure a manager can view supersedes page and has an edit button"""
        self.login_ramanager()
        response = self.reverse_get(
            'aristotle_mdr_review_requests:request_supersedes',
            reverse_args=[self.review.id]
        )
        self.assertEqual(response.status_code, 200)
        can_edit = response.context['can_edit_review']
        self.assertEqual(can_edit, True)

    def test_superseded_date_in_info_box_for_supersede_via_review(self):
        """ Confirm that when a supersedes is created via review, the date at which the supersedes was applied
        appears in the concept infobox """

        # Add second item to review
        second_item = self.create_editor_item(name='Person', definition="A human being")

        self.review.concepts.add(second_item)

        # Create items to be used in supersedes tab, all are Object Classes
        older_item = self.create_editor_item('Old Person', 'A person that is very old')

        # Post data
        data = [
            {'older_item': older_item.id,
             'newer_item': self.item.id,
             'message': 'Supersede this!',
             'date_effective': datetime.date(2019, 1, 1)
             },
        ]
        response = self.post_formset(data, 0)

        # Check that the pages redirects
        self.assertEqual(response.status_code, 302)

        # Accept the review
        wizard_data = [
            {'status_message': 'This review is approved', 'close_review': '1'},
            {'selected_list': [str(self.item.id)]}
        ]

        self.login_registrar()
        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_review_requests:accept_review', args=[self.review.id]),
            'review_accept_view',
            ['review_accept', 'review_changes']
        )
        self.assertEqual(response.status_code, 302)

        # Caching ...
        self.review.refresh_from_db()
        # Check that the review was approved, and changed to an 'Approved' state

        self.assertEqual(self.review.status, REVIEW_STATES.approved)
        response = self.reverse_get(
            'aristotle:item',
            reverse_args=[self.item.id, 'objectclass', 'my-object'],  # Slug for self.item
            status_code=200
        )
        # Check the item to see if date_effective is set
        older_item = response.context['item']

        supersedes_relation = older_item.superseded_items_relation_set.first()

        self.assertEqual(supersedes_relation.date_effective, datetime.date(2019, 1, 1))


@skip('Needs to be updated for new reviews system')
class ReviewRequestPermissions(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()
        self.other_ra = MDR.RegistrationAuthority.objects.create(name="Other RA")
        self.other_registrar = User.objects.create(email="otto@other-register.com")
        self.other_ra.registrars.add(self.other_registrar)

        review = self.make_review_request_iterable(
            [],
            request_kwargs={
                "requester": self.viewer,
                "title": "My Review",
                "target_registration_state": MDR.STATES.standard,
                "registration_date": "2018-01-01",
            }
        )

    def test_user_can_view_review(self):
        perm = perms.user_can_view_review

        self.assertTrue(perm(self.viewer, self.review_request))
        self.assertTrue(perm(self.registrar, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

        # Revoke review
        self.review_request.status = REVIEW_STATES.revoked

        self.assertTrue(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

    def test_user_can_approve_review(self):
        perm = perms.user_can_approve_review
        self.assertTrue(perm(self.registrar, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertFalse(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

        # Closed review
        self.review_request.status = REVIEW_STATES.closed
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertFalse(perm(self.su, self.review_request))
        self.assertFalse(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

        # Revoked review
        self.review_request.status = REVIEW_STATES.revoked
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertFalse(perm(self.su, self.review_request))
        self.assertFalse(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

        # Approved review
        self.review_request.status = REVIEW_STATES.approved
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertFalse(perm(self.su, self.review_request))
        self.assertFalse(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

    def test_user_can_close_or_reopen_review(self):
        perm = perms.user_can_close_or_reopen_review
        self.assertTrue(perm(self.registrar, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertTrue(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

        # Revoked review
        self.review_request.status = REVIEW_STATES.revoked
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertTrue(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

    def test_user_can_edit_review(self):
        perm = perms.user_can_edit_review

        self.assertTrue(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertTrue(perm(self.ramanager, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))

        # Revoke review
        self.review_request.status = REVIEW_STATES.revoked

        self.assertTrue(perm(self.viewer, self.review_request))
        self.assertFalse(perm(self.registrar, self.review_request))
        self.assertFalse(perm(self.ramanager, self.review_request))
        self.assertTrue(perm(self.su, self.review_request))
        self.assertFalse(perm(self.editor, self.review_request))
        self.assertFalse(perm(self.other_registrar, self.review_request))


class ReviewRequestActionsPage(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()

        # There would be too many tests to test every item type against every other
        # But they all have identical logic, so one test should suffice
        self.item1 = MDR.ObjectClass.objects.create(name="Test Item 1 (visible to tested viewers)", definition="my definition", workgroup=self.wg1)
        self.item2 = MDR.ObjectClass.objects.create(name="Test Item 2 (NOT visible to tested viewers)", definition="my definition", workgroup=self.wg2)
        self.item3 = MDR.ObjectClass.objects.create(name="Test Item 3 (only visible to the editor)", definition="my definition", workgroup=None, submitter=self.editor)

        self.item4 = MDR.ValueDomain.objects.create(name='Test Value Domain', definition='my definition', workgroup=self.wg1)
        self.item5 = MDR.DataElement.objects.create(name='Test data element', definition='my definition', workgroup=self.wg1, valueDomain=self.item4)

    def check_item_status(self, item, review, updated):

        self.assertEqual(item.is_public(), updated)
        self.assertEqual(item.current_statuses().count() == 1, updated)

        if updated:
            state = item.current_statuses().first()

            self.assertTrue(state.registrationAuthority == review.registration_authority)
            self.assertTrue(state.state == review.state)
            self.assertTrue(state.effective_date == review.registration_date)
        else:
            self.assertTrue(item.current_statuses().count() == 0)

    def make_public_rr(self, items, ra=None, user=None):
        if not user:
            user = self.editor

        if ra is None:
            ra = self.ra

        review = models.ReviewRequest.objects.create(
            requester=user,
            registration_authority=ra,
            target_registration_state=ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )
        review.concepts = items
        review.save()
        return review

    def post_public_rr(self, items, ra=None):
        if ra is None:
            ra = self.ra
        response = self.client.post(
            reverse('aristotle_reviews:review_create'),
            {
                'concepts': [i.pk for i in items],
                'registration_authority': ra.id,
                'target_registration_state': self.ra.public_state,
                'cascade_registration': 0,
                'title': "Please review this",
                'registration_date': datetime.date(2010, 1, 1)
            }
        )
        return response

    def check_urls(self, review_pk, urls, status_code):
        for url in urls:
            try:
                response = self.client.get(
                    reverse(url, args=[review_pk])
                )
                self.assertEqual(response.status_code, status_code)
            except:  # pragma: no cover
                print(url)
                print(response)
                raise

    def test_viewer_can_request_review(self):
        self.login_editor()

        response = self.client.get(reverse('aristotle_reviews:review_create'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.item1.rr_review_requests.count(), 0)
        request = self.make_public_rr([self.item1])
        self.assertEqual(self.item1.rr_review_requests.count(), 1)

        self.check_urls(request.pk, review_urls, 200)
        self.check_urls(request.pk, review_edit_urls, 200)
        self.check_urls(request.pk, review_accept_urls, 403)

        # Can't see, can't review others reviews
        self.assertEqual(self.item2.rr_review_requests.count(), 0)
        request = self.make_public_rr([self.item2], user=self.viewer)
        self.assertEqual(self.item2.rr_review_requests.count(), 1)
        self.assertEqual(self.item2.rr_review_requests.visible(self.editor).count(), 0)
        self.check_urls(request.pk, review_urls, 403)

        # Cant post
        response = self.post_public_rr([self.item2])
        self.assertEqual(self.item2.rr_review_requests.count(), 1)

        self.assertTrue("concepts" in response.context['form'].errors.keys())
        self.assertTrue(
            "{} is not one of the available choices".format(self.item2.pk)
            in str(response.context['form'].errors['concepts'])
        )
        self.assertEqual(self.item2.rr_review_requests.count(), 1)

    def test_registrar_can_view_review(self):
        self.login_registrar()

        self.assertEqual(self.item1.rr_review_requests.count(), 0)
        request = self.make_public_rr([self.item1])
        self.assertEqual(self.item1.rr_review_requests.count(), 1)

        review_pk = request.pk

        self.check_urls(review_pk, review_urls, 200)
        self.check_urls(review_pk, review_edit_urls, 403)
        self.check_urls(review_pk, review_accept_urls, 200)


@skip('All these tests need to be updated for new reviews system')
class OldReviewRequestActionsPage(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()

        # There would be too many tests to test every item type against every other
        # But they all have identical logic, so one test should suffice
        self.item1 = MDR.ObjectClass.objects.create(name="Test Item 1 (visible to tested viewers)", definition="my definition", workgroup=self.wg1)
        self.item2 = MDR.ObjectClass.objects.create(name="Test Item 2 (NOT visible to tested viewers)", definition="my definition", workgroup=self.wg2)
        self.item3 = MDR.ObjectClass.objects.create(name="Test Item 3 (only visible to the editor)", definition="my definition", workgroup=None, submitter=self.editor)

        self.item4 = MDR.ValueDomain.objects.create(name='Test Value Domain', definition='my definition', workgroup=self.wg1)
        self.item5 = MDR.DataElement.objects.create(name='Test data element', definition='my definition', workgroup=self.wg1, valueDomain=self.item4)

    def check_item_status(self, item, review, updated):

        self.assertEqual(item.is_public(), updated)
        self.assertEqual(item.current_statuses().count() == 1, updated)

        if updated:
            state = item.current_statuses().first()

            self.assertTrue(state.registrationAuthority == review.registration_authority)
            self.assertTrue(state.state == review.state)
            self.assertTrue(state.effective_date == review.registration_date)
        else:
            self.assertTrue(item.current_statuses().count() == 0)

    def post_public_rr(self, items, ra=None):
        if ra is None:
            ra = self.ra
        response = self.client.post(
            reverse('aristotle_reviews:review_create'),
            {
                'concepts': [i.pk for i in items],
                'registration_authority': ra.id,
                'target_registration_state': self.ra.public_state,
                'cascade_registration': 0,
                'title': "Please review this",
                'registration_date': datetime.date(2010, 1, 1)
            }
        )
        return response

    def check_urls(self, review_pk, urls, status_code):
        for url in urls:
            try:
                response = self.client.get(
                    reverse(url, args=[review_pk])
                )
                self.assertEqual(response.status_code, status_code)
            except:  # pragma: no cover
                print(url)
                print(response)
                raise

    def test_viewer_can_request_review(self):
        self.login_editor()

        response = self.client.get(reverse('aristotle_reviews:review_create'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.item1.rr_review_requests.count(), 0)
        response = self.post_public_rr([self.item1])
        self.assertEqual(self.item1.rr_review_requests.count(), 1)

        review_pk = response.url.rstrip("/").rsplit("/")[-2]

        # response = self.client.get(
        #     reverse('aristotle_reviews:review_list'),
        #     args=[review_pk]
        # )
        self.check_urls(review_pk, review_urls, 200)
        self.check_urls(review_pk, review_edit_urls, 403)
        self.check_urls(review_pk, review_accept_urls, 403)

        # Can't see, can't reviews
        self.assertEqual(self.item2.rr_review_requests.count(), 0)
        response = self.post_public_rr([self.item2])
        self.assertEqual(self.item2.rr_review_requests.count(), 0)

        self.assertTrue("concepts" in response.context['form'].errors.keys())
        self.assertTrue(
            "{} is not one of the available choices".format(self.item2.pk)
            in str(response.context['form'].errors['concepts'])
        )

    def test_registrar_can_view_review(self):
        self.login_editor()

        self.assertEqual(self.item1.rr_review_requests.count(), 0)
        response = self.post_public_rr([self.item1])
        self.assertEqual(self.item1.rr_review_requests.count(), 1)

        review_pk = response.url.rstrip("/").rsplit("/")[-2]

        self.login_registrar()

        self.check_urls(review_pk, review_urls, 200)
        self.check_urls(review_pk, review_accept_urls, 200)

    def test_registrar_cant_view_other_ra_reviews(self):
        self.login_editor()

        other_ra = MDR.RegistrationAuthority.objects.create(name="Other RA!", definition="")

        self.assertEqual(self.item1.rr_review_requests.count(), 0)
        response = self.post_public_rr([self.item1], ra=other_ra)
        self.assertEqual(self.item1.rr_review_requests.count(), 1)

        review_pk = response.url.rstrip("/").rsplit("/")[-2]

        self.login_registrar()

        self.check_urls(review_pk, review_rls, 403)
        self.check_urls(review_pk, review_accept_urls, 403)

    def test_registrar_has_valid_items_in_review(self):

        item1 = MDR.ObjectClass.objects.create(name="Test Item 1", definition="my definition", workgroup=self.wg1)
        item2 = MDR.ObjectClass.objects.create(name="Test Item 2", definition="my definition", workgroup=self.wg2)
        item3 = MDR.ObjectClass.objects.create(name="Test Item 3", definition="my definition", workgroup=self.wg1)
        item4 = MDR.ObjectClass.objects.create(name="Test Item 4", definition="my definition", workgroup=self.wg2)

        self.login_registrar()

        response = self.client.get(reverse('aristotle:userReadyForReview',))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context['page']), 0)

        review = self.make_review_request_iterable([item1, item4], request_kwargs=dict(
            requester=self.su,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        response = self.client.get(reverse('aristotle:userReadyForReview',))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page']), 1)

        review = self.make_review_request_iterable([item1], request_kwargs=dict(
            requester=self.su,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        response = self.client.get(reverse('aristotle:userReadyForReview',))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page']), 2)

        other_ra = MDR.RegistrationAuthority.objects.create(name="A different ra")

        review = self.make_review_request_iterable([item2], request_kwargs=dict(
            requester=self.su,
            registration_authority=other_ra,
            target_registration_state=other_ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        response = self.client.get(reverse('aristotle:userReadyForReview',))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page']), 2)

        other_ra.giveRoleToUser('registrar', self.registrar)
        response = self.client.get(reverse('aristotle:userReadyForReview',))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page']), 3)

    def test_superuser_can_see_review(self):
        self.login_superuser()
        other_ra = MDR.RegistrationAuthority.objects.create(name="A different ra", stewardship_organisation=self.steward_org)

        review = self.make_review_request_iterable([item2], request_kwargs=dict(
            requester=self.editor,
            registration_authority=other_ra,
            target_registration_state=other_ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review.status = REVIEW_STATES.revoked
        review.save()

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

    def test_registrar_can_see_review(self):
        self.login_registrar()
        other_ra = MDR.RegistrationAuthority.objects.create(name="A different ra")

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=other_ra,
            state=other_ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 404)

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review.status = REVIEW_STATES.revoked
        review.save()

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 404)

    def test_anon_cannot_see_review(self):

        review = self.make_review_request_iterable([self.item1], request_kwargs=dict(
            requester=self.editor,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        # logged out user cannot see request
        self.logout()
        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 302)
        # is redirected to login

    def test_editor_can_see_review(self):
        self.login_editor()

        review = self.make_review_request_iterable([self.item1], request_kwargs=dict(
            requester=self.editor,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review.status = REVIEW_STATES.revoked
        review.save()

        response = self.client.get(reverse('aristotle_reviews:review_details', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

    def registrar_can_accept_review(self, review_changes=False):
        self.login_registrar()
        other_ra = MDR.RegistrationAuthority.objects.create(name="A different ra")

        review = self.make_review_request_iterable([self.item1], request_kwargs=dict(
            requester=self.editor,
            registration_authority=other_ra,
            target_registration_state=other_ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertEqual(response.status_code, 403)

        review = self.make_review_request_iterable([self.item1, self.item2], request_kwargs=dict(
            requester=self.editor,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review.status = REVIEW_STATES.revoked
        review.save()

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse('aristotle:userReviewAccept', args=[review.pk]),
            {
                'review_accept-response': "I can't accept this, its revoked",
                'review_accept_view-current_step': 'review_accept',
                'submit_skip': 'value',
            }
        )

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        self.assertEqual(response.status_code, 403)
        self.assertEqual(review.status, REVIEW_STATES.revoked)
        self.assertFalse(bool(review.response))

        review.status = REVIEW_STATES.submitted
        review.save()

        self.assertTrue(self.item1.current_statuses().count() == 0)

        self.item1 = MDR.ObjectClass.objects.get(pk=self.item1.pk)  # decache
        self.assertFalse(self.item1.is_public())

        if review_changes:
            button = "submit_next"
        else:
            button = "submit_skip"

        response = self.client.post(
            reverse('aristotle:userReviewAccept', args=[review.pk]),
            {
                'review_accept-response': "I can accept this!",
                'review_accept_view-current_step': 'review_accept',
                button: 'value',
            }
        )

        if review_changes:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['wizard']['steps'].step1, 2)  # check we are now on second setep
            selected_for_change = [self.item1.id]
            selected_for_change_strings = [str(a) for a in selected_for_change]

            review_response = self.client.post(
                reverse('aristotle:userReviewAccept', args=[review.pk]),
                {
                    'review_changes-selected_list': selected_for_change_strings,
                    'review_accept_view-current_step': 'review_changes'
                }
            )

            self.assertRedirects(review_response, reverse('aristotle:userReadyForReview'))

        else:
            self.assertRedirects(response, reverse('aristotle:userReadyForReview'))

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        self.assertEqual(review.response, "I can accept this!")
        self.assertEqual(review.status, REVIEW_STATES.accepted)
        self.assertEqual(review.reviewer, self.registrar)

        self.item1 = MDR.ObjectClass.objects.get(pk=self.item1.pk)  # decache
        self.item2 = MDR.ObjectClass.objects.get(pk=self.item2.pk)  # decache

        if review_changes:
            updated_items = [self.item1.pk]
        else:
            updated_items = [self.item1.pk, self.item2.pk]

        for item in [self.item1, self.item2]:
            if item.id in updated_items:
                updated = True
            else:
                updated = False

            self.check_item_status(item, review, updated)

    @tag('changestatus')
    def test_registrar_can_accept_review_direct(self):
        self.registrar_can_accept_review(review_changes=False)

    @tag('changestatus')
    def test_registrar_can_accept_review_alter_changes(self):
        self.registrar_can_accept_review(review_changes=True)

    def test_registrar_can_reject_review(self):
        self.login_registrar()
        other_ra = MDR.RegistrationAuthority.objects.create(name="A different ra")

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=other_ra,
            state=other_ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle:userReviewReject', args=[review.pk]))
        self.assertEqual(response.status_code, 403)

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle:userReviewReject', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review.status = REVIEW_STATES.revoked
        review.save()

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        response = self.client.get(reverse('aristotle:userReviewReject', args=[review.pk]))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse('aristotle:userReviewReject', args=[review.pk]),
            {
                'response': "I can't reject this, its revoked"
            }
        )

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        self.assertEqual(response.status_code, 403)
        self.assertEqual(review.status, REVIEW_STATES.revoked)
        self.assertFalse(bool(review.response))

        review.status = REVIEW_STATES.submitted
        review.save()

        response = self.client.post(
            reverse('aristotle:userReviewReject', args=[review.pk]),
            {
                'response': "I can reject this!",
            }
        )
        self.assertRedirects(response, reverse('aristotle:userReadyForReview',))

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        self.assertEqual(review.response, "I can reject this!")
        self.assertEqual(review.status, REVIEW_STATES.rejected)
        self.assertEqual(review.reviewer, self.registrar)

        self.item1 = MDR.ObjectClass.objects.get(pk=self.item1.pk)  # decache
        self.assertFalse(self.item1.is_public())

    # Function used by the 2 tests below
    def registrar_can_accept_cascade_review(self, review_changes=True):
        self.login_registrar()

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1),
            cascade_registration=1,
        )

        review.concepts.add(self.item5)

        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        if review_changes:
            button = 'submit_next'
        else:
            button = 'submit_skip'

        response = self.client.post(
            reverse('aristotle:userReviewAccept', args=[review.pk]),
            {
                'review_accept-response': "I can accept this!",
                'review_accept_view-current_step': 'review_accept',
                button: 'value',
            }
        )

        if review_changes:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['wizard']['steps'].step1, 2)  # check we are now on second setep
            selected_for_change = [self.item4.id, self.item5.id]
            selected_for_change_strings = [str(a) for a in selected_for_change]

            review_response = self.client.post(
                reverse('aristotle:userReviewAccept', args=[review.pk]),
                {
                    'review_changes-selected_list': selected_for_change_strings,
                    'review_accept_view-current_step': 'review_changes'
                }
            )

            self.assertRedirects(review_response, reverse('aristotle:userReadyForReview'))

        else:
            self.assertEqual(response.status_code, 302)

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        self.assertEqual(review.response, "I can accept this!")
        self.assertEqual(review.status, REVIEW_STATES.accepted)
        self.assertEqual(review.reviewer, self.registrar)

        self.item4 = models.ValueDomain.objects.get(pk=self.item4.pk)  # decache
        self.item5 = models.DataElement.objects.get(pk=self.item5.pk)  # decache

        for item in [self.item4, self.item5]:
            self.check_item_status(item, review, True)

    @tag('changestatus')
    def test_registrar_can_accept_cascade_review_direct(self):
        self.registrar_can_accept_review(review_changes=False)

    @tag('changestatus')
    def test_registrar_can_accept_cascade_review_revstep(self):
        self.registrar_can_accept_review(review_changes=True)

    def test_user_can_cancel_review(self):
        self.login_editor()

        review = models.ReviewRequest.objects.create(
            requester=self.viewer,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle:userReviewCancel', args=[review.pk]))
        self.assertEqual(response.status_code, 403)

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle:userReviewCancel', args=[review.pk]))
        self.assertEqual(response.status_code, 200)

        review.status = REVIEW_STATES.revoked
        review.save()

        response = self.client.get(reverse('aristotle:userReviewCancel', args=[review.pk]))
        self.assertRedirects(response, reverse('aristotle_reviews:review_details', args=[review.pk]))

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        self.assertFalse(review.status == REVIEW_STATES.revoked)
        response = self.client.post(reverse('aristotle:userReviewCancel', args=[review.pk]), {})
        self.assertRedirects(response, reverse('aristotle:userMyReviewRequests',))

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache
        self.assertTrue(review.status == REVIEW_STATES.revoked)

    def test_registrar_cant_load_rejected_or_accepted_review(self):
        self.login_registrar()
        MDR.RegistrationAuthority.objects.create(name="A different ra")

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            status=REVIEW_STATES.accepted,
            target_registration_state=models.STATES.standard,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle:userReviewReject', args=[review.pk]))
        self.assertRedirects(response, reverse('aristotle_mdr:review_details', args=[review.pk]))

        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertRedirects(response, reverse('aristotle_mdr:review_details', args=[review.pk]))

        review = models.ReviewRequest.objects.create(
            requester=self.editor,
            registration_authority=self.ra,
            status=REVIEW_STATES.rejected,
            target_registration_state=models.STATES.standard,
            registration_date=datetime.date(2010, 1, 1)
        )

        review.concepts.add(self.item1)

        response = self.client.get(reverse('aristotle:userReviewReject', args=[review.pk]))
        self.assertRedirects(response, reverse('aristotle_mdr:review_details', args=[review.pk]))

        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertRedirects(response, reverse('aristotle_mdr:review_details', args=[review.pk]))

        review = self.make_review_request(self.item1, self.registrar, requester=self.editor)

        response = self.client.get(reverse('aristotle:userReviewReject', args=[review.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertEqual(response.status_code, 403)

    def test_who_can_see_review(self):
        from aristotle_mdr.perms import user_can_view_review

        review = self.make_review_request(self.item1, self.registrar, requester=self.editor)

        self.assertTrue(user_can_view_review(self.editor, review))
        self.assertTrue(user_can_view_review(self.registrar, review))
        self.assertTrue(user_can_view_review(self.su, review))
        self.assertFalse(user_can_view_review(self.viewer, review))

        review.status = REVIEW_STATES.revoked
        review.save()

        review = models.ReviewRequest.objects.get(pk=review.pk)  # decache

        self.assertTrue(user_can_view_review(self.editor, review))
        self.assertFalse(user_can_view_review(self.registrar, review))
        self.assertTrue(user_can_view_review(self.su, review))
        self.assertFalse(user_can_view_review(self.viewer, review))

    def test_notifications(self):
        viewer_num_notifications = self.viewer.notifications.count()
        registrar_num_notifications = self.registrar.notifications.count()
        editor_num_notifications = self.editor.notifications.count()

        review = self.make_review_request_iterable([], request_kwargs=dict(
            requester=self.viewer,
            registration_authority=self.ra,
            target_registration_state=self.ra.public_state,
            registration_date=datetime.date(2010, 1, 1)
        ))

        # Review requested, does a registrar get the notification?
        self.assertTrue(self.viewer.notifications.count() == viewer_num_notifications)
        self.assertTrue(self.registrar.notifications.count() == registrar_num_notifications + 1)
        self.assertTrue(self.editor.notifications.count() == editor_num_notifications)

        self.assertTrue(self.registrar.notifications.first().target == review)

        review.status = REVIEW_STATES.accepted
        review.save()

        # Review updated, does the requester get the notification?
        self.assertTrue(self.viewer.notifications.count() == viewer_num_notifications + 1)
        self.assertTrue(self.registrar.notifications.count() == registrar_num_notifications + 1)
        self.assertTrue(self.editor.notifications.count() == editor_num_notifications)

        self.assertTrue(self.viewer.notifications.first().target == review)

    @tag('inactive_ra')
    def test_cannot_create_rr_against_incative_ra(self):
        self.login_editor()
        self.ra.active = 1
        self.ra.save()

        self.assertEqual(self.item1.rr_review_requests.count(), 0)

        response = self.post_public_rr([self.item1])
        self.assertEqual(response.status_code, 200)
        self.assertTrue('registrationAuthorities' in response.context['form'].errors)
        self.assertEqual(self.item1.rr_review_requests.count(), 0)

    @tag('inactive_ra')
    def test_cannot_accept_rr_with_inactive_ra(self):
        self.login_editor()

        # Create review request
        response = self.post_public_rr([self.item3])
        self.assertEqual(self.item3.rr_review_requests.count(), 1)
        review = self.item3.rr_review_requests.all()[0]

        # Make ra inactive
        self.ra.active = 1
        self.ra.save()

        response = self.client.get(reverse('aristotle:userReviewAccept', args=[review.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse('aristotle:userReviewAccept', args=[review.pk]),
            {
                'review_accept-response': "I can accept this!",
                'review_accept_view-current_step': 'review_accept',
                'submit_skip': 'value',
            }
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.item3.rr_review_requests.count(), 1)

    @tag('inactive_ra')
    def test_reviews_hidden_from_lists_when_ra_inactive(self):
        self.login_viewer()

        # Create review request
        response = self.post_public_rr([self.item1])
        self.assertEqual(self.item1.rr_review_requests.count(), 1)

        # Make ra inactive
        self.ra.active = 1
        self.ra.save()

        # My review requests
        response = self.client.get(reverse('aristotle_mdr:userMyReviewRequests'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['reviews']), 0)

        # Registrar Review list
        self.login_registrar()
        response = self.client.get(reverse('aristotle_mdr:userReadyForReview'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['reviews']), 0)


class ReviewsFormsTest(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()

        cache.clear()

    def test_inactive_registration_authoritites_dont_appear_as_options_in_form(self):
        self.login_regular_user()
        self.item1 = MDR.ObjectClass.objects.create(
            name="Test Item 1", definition="my definition")
        self.my_active_ra = MDR.RegistrationAuthority.objects.create(name="My Active RA",
                                                                     definition="",
                                                                     stewardship_organisation=self.steward_org_1,
                                                                     active=0)
        self.my_inactive_ra = MDR.RegistrationAuthority.objects.create(name="My Inactive RA",
                                                                       definition="",
                                                                       stewardship_organisation=self.steward_org_1,
                                                                       active=1)
        self.my_hidden_ra = MDR.RegistrationAuthority.objects.create(name="My Hidden RA",
                                                                     definition="",
                                                                     stewardship_organisation=self.steward_org_1,
                                                                     active=2)

        self.review_request = ReviewRequest.objects.create(registration_authority=self.my_active_ra, requester_id=self.newuser.id)
        self.form = RequestReviewCreateForm(
            user=self.newuser
        )
        self.form.instance = self.review_request

        self.assertIn(self.my_active_ra, self.form.fields['registration_authority'].queryset)
        self.assertNotIn(self.my_inactive_ra, self.form.fields['registration_authority'].queryset)
        self.assertNotIn(self.my_hidden_ra, self.form.fields['registration_authority'].queryset)
