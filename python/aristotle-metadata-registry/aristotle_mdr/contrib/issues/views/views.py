import json
import difflib
from django.http import Http404
from django.db.models import Q
from django.views.generic import TemplateView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from aristotle_mdr.views.utils import SimpleItemGet
from aristotle_mdr.contrib.issues.models import Issue, IssueLabel
from aristotle_mdr import perms


class IssueBase(LoginRequiredMixin, SimpleItemGet):

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['activetab'] = 'issues'
        context['hide_item_actions'] = True
        return context

    def get_modal_data(self, issue=None):
        """Get data for issue modal creation and editing"""
        # Get field data for proposable fields on concept
        field_data = {}
        for fname, oname in Issue.proposable_fields:
            value = getattr(self.item, fname, '')
            field_data[fname] = value

        data = {}
        if issue:
            data['proposal_field'] = issue.proposal_field
            data['proposal_value'] = issue.proposal_value
            data['name'] = issue.name
            data['description'] = issue.description
            data['labels'] = list(issue.labels.all().values_list('id', flat=True))

        # Fetch issue labels
        this_so_or_none = (
            Q(stewardship_organisation__isnull=True) |
            Q(stewardship_organisation=self.item.stewardship_organisation)
        )
        labels = IssueLabel.objects.filter(this_so_or_none)
        label_map = {l.pk: l.label for l in labels}

        return {
            'fields': json.dumps(Issue.get_propose_fields()),
            'field_data': json.dumps(field_data),
            'initial': json.dumps(data),
            'editor_config': json.dumps(settings.CKEDITOR_CONFIGS['default']),
            'all_labels': json.dumps(label_map)
        }


class IssueList(IssueBase, TemplateView):
    template_name = 'aristotle_mdr/issues/list.html'

    def get_issues(self):
        open_issues = self.item.issues.filter(isopen=True).order_by('created').prefetch_related('labels')
        closed_issues = self.item.issues.filter(isopen=False).order_by('created').prefetch_related('labels')
        return open_issues, closed_issues

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        # Fetch issues for the item
        open_issues, closed_issues = self.get_issues()
        # Update context
        stewardship_organisation_name = ""
        if self.item.stewardship_organisation:
            stewardship_organisation_name = self.item.stewardship_organisation.name
        context.update({
            'open_issues': open_issues,
            'closed_issues': closed_issues,
            'stewardship_organisation_name': stewardship_organisation_name,
        })
        # Update context with modal data
        context.update(self.get_modal_data())
        return context


class IssueDisplay(IssueBase, TemplateView):
    template_name = 'aristotle_mdr/issues/display.html'

    def get_issue(self):
        try:
            issue = Issue.objects.get(
                pk=self.kwargs['pk'],
                item=self.item
            )
        except Issue.DoesNotExist:
            issue = None

        return issue

    def get(self, request, *args, **kwargs):
        item = self.get_item(request.user)

        self.item = item
        self.issue = self.get_issue()
        if not self.issue:
            raise Http404

        return super(IssueBase, self).get(request, *args, **kwargs)

    def get_diff_table(self, prop_field, prop_value):
        differ = difflib.HtmlDiff(wrapcolumn=50)

        old = getattr(self.item, prop_field)
        old_lines = old.split('\n')
        new_lines = prop_value.split('\n')

        return differ.make_table(old_lines, new_lines, context=True, numlines=5)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        # Set objects
        context['object'] = self.issue
        context['comments'] = self.issue.comments.select_related(
            'author__profile'
        ).all().order_by('created')
        # Set permissions
        can_edit_item = perms.user_can_edit(self.request.user, self.issue.item)
        own_issue = (self.request.user.id == self.issue.submitter.id)
        has_proposed_changes = (self.issue.proposal_field and self.issue.proposal_value)
        item_changed = self.issue.modified < self.issue.item.modified
        context.update({
            'can_open_close': (own_issue or can_edit_item),
            'own_issue': own_issue,
            'can_approve': can_edit_item,
            'has_proposed_changes': has_proposed_changes,
            'item_changed': item_changed,
            # Loaded by root component
            'issue_data': {'isopen': self.issue.isopen},
        })
        # Add diff table
        diff_table = ''
        if has_proposed_changes:
            diff_table = self.get_diff_table(self.issue.proposal_field, self.issue.proposal_value)
        context['diff_table'] = diff_table
        # Get data for modal
        context.update(self.get_modal_data(self.issue))
        return context
