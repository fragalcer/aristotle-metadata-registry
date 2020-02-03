from django.test import TestCase
from django.urls import reverse

from aristotle_mdr.tests.utils import AristotleTestUtils
from aristotle_mdr import models as mdr_models
from aristotle_mdr.contrib.issues import models
from aristotle_mdr.contrib.stewards.tests.test_perms import BaseStewardOrgsTestCase


class IssueTests(AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.item = mdr_models.ObjectClass.objects.create(
            name='Test Item',
            definition='Just a test item',
            workgroup=self.wg1
        )

    def create_test_issue(self, name='Test Issue', user=None):
        if not user:
            user = self.editor
        return models.Issue.objects.create(
            name=name,
            description='Just a test',
            item=self.item,
            submitter=user
        )

    def test_issue_create(self):
        issue = self.create_test_issue()
        self.assertTrue(issue.isopen)
        self.assertIsNotNone(issue.created)

    def test_issue_displays(self):
        self.create_test_issue()
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_issues:item_issues',
            reverse_args=[self.item.id],
            status_code=200
        )
        self.assertEqual(response.context['activetab'], 'issues')

        issues = response.context['issues']
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].name, 'Test Issue')

    def test_issues_list_open_closed(self):
        openis = self.create_test_issue()
        closedis = self.create_test_issue()
        closedis.isopen = False
        closedis.save()

        self.login_viewer()
        response = self.reverse_get(
            'aristotle_issues:item_issues',
            reverse_args=[self.item.id],
            status_code=200
        )
        context = response.context

        self.assertEqual(len(context['open_issues']), 1)
        self.assertEqual(len(context['closed_issues']), 1)

        self.assertEqual(context['open_issues'][0].id, openis.id)
        self.assertEqual(context['closed_issues'][0].id, closedis.id)

    def test_own_issue_true_on_own_issue(self):
        issue = self.create_test_issue()
        self.login_editor()

        response = self.reverse_get(
            'aristotle_issues:issue',
            reverse_args=[self.item.id, issue.pk],
            status_code=200
        )

        self.assertTrue(response.context['own_issue'])

    def test_own_issue_false_on_othes_issue(self):
        issue = self.create_test_issue()
        self.login_viewer()

        response = self.reverse_get(
            'aristotle_issues:issue',
            reverse_args=[self.item.id, issue.pk],
            status_code=200
        )

        self.assertFalse(response.context['own_issue'])

    def test_editor_user_can_accept_proposed_changes(self):
        issue = self.create_test_issue(self.viewer)
        self.login_editor()

        response = self.reverse_get(
            'aristotle_issues:issue',
            reverse_args=[self.item.id, issue.pk],
            status_code=200
        )
        self.assertTrue(response.context['can_open_close'])

    def test_regular_user_cannot_accept_proposed_changes(self):
        issue = self.create_test_issue()
        self.make_item_public(self.item, self.ra)
        self.login_regular_user()

        response = self.reverse_get(
            'aristotle_issues:issue',
            reverse_args=[self.item.id, issue.pk],
            status_code=200
        )
        self.assertFalse(response.context['can_open_close'])

    def test_view_issue_invalid_item(self):
        issue = self.create_test_issue()

        self.login_editor()
        response = self.reverse_get(
            'aristotle_issues:issue',
            reverse_args=[70000, issue.pk],
            status_code=404
        )

    def test_view_issue_no_perm_item(self):
        issue = self.create_test_issue()

        self.login_regular_user()
        response = self.reverse_get(
            'aristotle_issues:issue',
            reverse_args=[self.item.id, issue.pk],
            status_code=403
        )

    def test_proposable_fields(self):
        fields = models.Issue.get_propose_fields()
        # Make sure all explicitly specified fields were added
        self.assertEqual(
            len(fields),
            len(models.Issue.proposable_fields)
        )
        # Check html set correctly
        self.assertEqual(fields[0]['name'], 'name')
        self.assertEqual(fields[0]['html'], False)
        self.assertEqual(fields[1]['name'], 'definition')
        self.assertEqual(fields[1]['html'], True)

    def test_reversion_object_is_created_when_issue_is_accepted_and_closed(self):

        test_issue = models.Issue.objects.create(
            name="Test Issue with proposal field and value.",
            description='Just a test.',
            item=self.item,
            submitter=self.editor,
            proposal_field="name",
            proposal_value="My new Issue Name",
        )
        test_issue.apply(self.editor)
        from reversion.models import Revision
        reversion_object = Revision.objects.last()
        self.assertEqual(len(Revision.objects.all()), 1)  # There is one revision object.
        self.assertEqual(reversion_object.comment, "Changed name. This change was proposed in issue #{}".format(test_issue.pk))
        self.assertEqual(self.item.name, "My new Issue Name")


class LabelTests(BaseStewardOrgsTestCase, AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        from aristotle_mdr.contrib.issues.models import IssueLabel

        self.rw_label = IssueLabel.objects.create(
            label="Registry-wide",
        )
        self.so_label = IssueLabel.objects.create(
            label="Just for the SO",
            stewardship_organisation=self.steward_org_1,
        )

    def test_super_label_permissions(self):
        self.login_superuser()

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.rw_label.id],
            status_code=200
        )

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.so_label.id],
            status_code=200
        )
        response = self.reverse_get('aristotle_issues:admin_labels_create', status_code=200)
        response = self.reverse_get('aristotle_issues:admin_issue_label_list', status_code=200)

    def test_so_manager_label_permissions(self):
        self.login_oscar()

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.rw_label.id],
            status_code=403
        )

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.so_label.id],
            status_code=200
        )
        response = self.reverse_get('aristotle_issues:admin_labels_create', status_code=200)
        response = self.reverse_get('aristotle_issues:admin_issue_label_list', status_code=200)

    def test_viewer_label_permissions(self):
        self.login_viewer()

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.rw_label.id],
            status_code=403
        )

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.so_label.id],
            status_code=403
        )
        response = self.reverse_get('aristotle_issues:admin_labels_create', status_code=403)
        response = self.reverse_get('aristotle_issues:admin_issue_label_list', status_code=403)

    def test_updating_public_label_permissions(self):
        """Tests that updating a label"""
        self.logout()

        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.rw_label.id],
            status_code=302
        )
        # Assert that updating a registry wide label redirects to login
        redirect_url = reverse('friendly_login') + '?next=' + reverse('aristotle_issues:admin_labels_update',
                                                                      args=[self.rw_label.id])
        self.assertRedirects(response, redirect_url)

        # Assert that updating a stewardship organisation only label redirects to login
        response = self.reverse_get(
            'aristotle_issues:admin_labels_update',
            reverse_args=[self.so_label.id],
            status_code=302
        )
        redirect_url = reverse('friendly_login') + '?next=' + reverse('aristotle_issues:admin_labels_update',
                                                                      args=[self.so_label.id])

        self.assertRedirects(response, redirect_url)

    def test_creating_public_label_redirects_to_login(self):
        self.logout()
        response = self.reverse_get('aristotle_issues:admin_labels_create', status_code=302)

    def test_listing_labels_redirects_to_login(self):
        self.logout()
        response = self.reverse_get('aristotle_issues:admin_issue_label_list', status_code=302)
