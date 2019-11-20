import reversion
import aristotle_mdr.models as MDR
import aristotle_mdr.contrib.favourites.models as fav_models
from typing import Any, Dict
from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.forms import HiddenInput
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from aristotle_mdr.forms import ChangeStatusForm
from aristotle_mdr.perms import (
    user_can_view,
    user_is_registrar,
    user_can_move_any_workgroup,
    user_can_move_any_stewardship_organisation,
    user_can_remove_from_stewardship_organisation,
    user_can_move_to_stewardship_organisation
)
from aristotle_mdr.forms.creation_wizards import UserAwareForm
from aristotle_mdr.contrib.autocomplete import widgets
from aristotle_mdr.utils import fetch_aristotle_downloaders


class ForbiddenAllowedModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def __init__(self, *args, **kwargs):
        self.validate_queryset = kwargs.pop('validate_queryset')
        super().__init__(*args, **kwargs)

    def _check_values(self, value):
        """
        Given a list of possible PK values, returns a QuerySet of the
        corresponding objects. Skips values if they are not in the queryset.
        This allows us to force a limited selection to the client, while
        ignoring certain additional values if given. However, this means
        *extra checking must be done* to limit over exposure and invalid
        data.
        """
        from django.core.exceptions import ValidationError
        from django.utils.encoding import force_text

        key = self.to_field_name or 'pk'
        # deduplicate given values to avoid creating many querysets or
        # requiring the database backend deduplicate efficiently.
        try:
            value = frozenset(value)
        except TypeError:
            # list of lists isn't hashable, for example
            raise ValidationError(
                self.error_messages['list'],
                code='list',
            )
        for pk in value:
            try:
                self.validate_queryset.filter(**{key: pk})
            except (ValueError, TypeError):
                raise ValidationError(
                    self.error_messages['invalid_pk_value'],
                    code='invalid_pk_value',
                    params={'pk': pk},
                )
        qs = self.validate_queryset.filter(**{'%s__in' % key: value})
        pks = set(force_text(getattr(o, key)) for o in qs)
        for val in value:
            if force_text(val) not in pks:
                raise ValidationError(
                    self.error_messages['invalid_choice'],
                    code='invalid_choice',
                    params={'value': val},
                )
        return qs


class RedirectBulkActionMixin:
    redirect = True

    def get_redirect_url(self):
        return self.redirect_url


class BulkActionForm(UserAwareForm):
    classes = ""
    redirect: bool = False
    confirm_page: Any = None
    all_in_queryset = forms.BooleanField(
        label=_("All items"),
        required=False,
        widget=HiddenInput()
    )
    qs = forms.CharField(
        label=_("All items"),
        required=False,
        widget=HiddenInput()
    )

    # Queryset is all as we try to be nice and process what we can in bulk actions.
    items = ForbiddenAllowedModelMultipleChoiceField(
        queryset=MDR._concept.objects.all(),
        validate_queryset=MDR._concept.objects.all(),
        label="Related items",
        required=False,
    )
    items_label = "Select some items"
    queryset = MDR._concept.objects.all()

    def __init__(self, form, *args, **kwargs):
        self.initial_items = kwargs.pop('items', [])

        self.request = kwargs.pop('request')
        if 'user' in kwargs.keys():
            self.user = kwargs.get('user', None)
            queryset = MDR._concept.objects.visible(self.user)
        else:
            queryset = MDR._concept.objects.public()

        if 'data' not in kwargs:
            super().__init__(form, *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

        self.fields['items'] = ForbiddenAllowedModelMultipleChoiceField(
            label=self.items_label,
            validate_queryset=MDR._concept.objects.all(),
            queryset=queryset,
            initial=self.initial_items,
            required=False,
            widget=widgets.ConceptAutocompleteSelectMultiple()
        )

    @property
    def items_to_change(self):
        if bool(self.cleaned_data.get('all_in_queryset', False)):
            filters = {}
            from aristotle_mdr.utils.cached_querysets import get_queryset_from_uuid
            items = get_queryset_from_uuid(self.cleaned_data.get('qs', ""), MDR._concept)

            _slice = {"low": items.query.low_mark, "high": items.query.high_mark}
            items.query.low_mark = 0
            items.query.high_mark = None
            items = items.filter(**filters).visible(self.user)
            items.query.set_limits(**_slice)
        else:
            items = self.cleaned_data.get('items')
        return items

    @classmethod
    def can_use(cls, user):
        return True

    @classmethod
    def text(cls):
        if hasattr(cls, 'action_text'):
            return cls.action_text
        from django.utils.text import camel_case_to_spaces
        txt = cls.__name__
        txt = txt.replace('Form', '')
        txt = camel_case_to_spaces(txt)
        return txt


class LoggedInBulkActionForm(BulkActionForm):
    @classmethod
    def can_use(cls, user):
        return user.is_active


class AddFavouriteForm(LoggedInBulkActionForm):
    classes = "fa-bookmark"
    action_text = _('Add favourite')
    items_label = "Items that will be added to your favourites list"

    def make_changes(self):
        items = self.items_to_change
        items = items.visible(self.user)

        fav_tag, created = fav_models.Tag.objects.get_or_create(
            profile=self.user.profile,
            primary=True,
        )

        num_items = 0
        bad_items = []
        for item in items:
            if not user_can_view(self.user, item):
                bad_items.append(str(item.id))
            else:
                favourite, created = fav_models.Favourite.objects.get_or_create(
                    tag=fav_tag,
                    item=item
                )
                if created:
                    num_items += 1

        message_text = "{} items favourited.".format(num_items)
        return _(message_text)


class RemoveFavouriteForm(LoggedInBulkActionForm):
    classes = "fa-minus-square"
    action_text = _('Remove favourite')
    items_label = "Items that will be removed from your favourites list"

    def make_changes(self):
        items = self.items_to_change
        favourites = fav_models.Favourite.objects.filter(
            tag__primary=True,
            tag__profile=self.user.profile,
            item__in=list(items)
        )
        favourites.delete()
        return '%(num_items)s items removed from favourites.' % {'num_items': favourites.count()}


class ChangeStateForm(ChangeStatusForm, BulkActionForm):
    confirm_page = "aristotle_mdr/actions/bulk_actions/change_status.html"
    classes = "fa-university"
    action_text = _('Change registration status')
    items_label = "These are the items that will be registered. " \
                  "Add or remove additional items with the autocomplete box."

    @classmethod
    def can_use(cls, user):
        return user_is_registrar(user)


class BulkMoveMetadataMixin:
    @staticmethod
    def generate_moving_message(org_name, successfully_moved_items: int, failed_items=None) -> str:
        if not failed_items:
            message = _("%(num_items)s items moved into the workgroup '%(new_wgs)s'.") % {
                'num_items': successfully_moved_items,
                'new_wgs': org_name
            }
        else:
            message = _(
                "%(num_items)s items moved into the workgroup '%(new_wgs)s'. \n"
                "Some items failed, they had the id's: %(bad_ids)s"
            ) % {
                'new_wgs': org_name,
                'num_items': successfully_moved_items,
                'bad_ids': ", ".join(failed_items),
            }
        return message


class ChangeWorkgroupForm(BulkActionForm, BulkMoveMetadataMixin):
    confirm_page = "aristotle_mdr/actions/bulk_actions/change_workgroup.html"
    classes = "fa-users"
    action_text = _('Change workgroup')
    items_label = "These are the items that will be moved between workgroups." \
                  " Add or remove additional items with the autocomplete box."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['workgroup'] = forms.ModelChoiceField(
            label="Workgroup to move items to",
            queryset=self.user.profile.workgroups
        )
        self.fields['changeDetails'] = forms.CharField(
            label="Change notes (optional)",
            required=False,
            widget=forms.Textarea
        )

    def make_changes(self):
        import reversion
        from aristotle_mdr.perms import user_can_remove_from_workgroup, user_can_move_to_workgroup

        new_workgroup = self.cleaned_data['workgroup']
        items = self.cleaned_data['items']

        if not user_can_move_to_workgroup(self.user, new_workgroup):
            raise PermissionDenied

        move_from_checks = {}  # Cache workgroup permissions as we check them to speed things up.

        failed = []
        success = []
        with transaction.atomic(), reversion.revisions.create_revision():
            reversion.revisions.set_user(self.user)
            for item in items:
                if item.workgroup:
                    can_move = move_from_checks.get(item.workgroup.pk, None)
                    if can_move is None:
                        can_move = user_can_remove_from_workgroup(self.user, item.workgroup)
                        move_from_checks[item.workgroup.pk] = can_move
                else:
                    can_move = True  # There is no workgroup, the user can move their own item.

                if not can_move:
                    failed.append(item)
                else:
                    success.append(item)
                    item.workgroup = new_workgroup
                    item.save()

            failed = list(set(failed))
            success = list(set(success))
            bad_items = sorted([str(i.id) for i in failed])

            return self.generate_moving_message(new_workgroup.name, len(success), failed_items=bad_items)

    @classmethod
    def can_use(cls, user):
        return user_can_move_any_workgroup(user)


class ChangeStewardshipOrganisationForm(BulkActionForm, BulkMoveMetadataMixin):
    confirm_page = "aristotle_mdr/actions/bulk_actions/change_stewardship_organisation.html"
    classes = "fa-sitemap"
    action_text = _("Change stewardship organisation")
    items_label = "These are the items that will be moved between workgroups." \
                  " Add or remove additional items within the autocomplete box. "
    move_from_checks: Dict[int, bool] = {}  # Cache the view permission to speed up the bulk view.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['steward_org'] = forms.ModelChoiceField(
            label="Stewardship Organisation to move items to ",
            queryset=self.user.profile.stewardship_organisations,
            widget=forms.Select(attrs={'class': 'form-control'}),
        )

        self.fields['changeDetails'] = forms.CharField(
            label="Change notes (optional)",
            required=False,
            widget=forms.Textarea(attrs={'class': 'form-control'})
        )

    def apply_move_permission_checking(self, item) -> bool:
        can_move_permission = self.move_from_checks.get(item.stewardship_organisation.pk, None)
        if can_move_permission is None:
            can_move_permission = user_can_remove_from_stewardship_organisation(self.user,
                                                                                item.stewardship_organisation)
            # Cache the can move permission
            self.move_from_checks[item.stewardship_organisation.pk] = can_move_permission
        else:
            can_move_permission = True  # No org, the user can move their own item.

        return can_move_permission

    def make_changes(self):
        self.move_from_checks = {}

        new_stewardship_org = self.cleaned_data['steward_org']
        # change_details = self.cleaned_data['changeDetails']
        items = self.cleaned_data['items']

        failed = []
        succeeded = []

        if not user_can_move_to_stewardship_organisation(self.user, new_stewardship_org):
            raise PermissionDenied

        with transaction.atomic(), reversion.revisions.create_revision():
            reversion.revisions.set_user(self.user)
            for item in items:
                if item.stewardship_organisation:  # The item has a stewardship organisation.
                    can_move_permission = self.apply_move_permission_checking(item)

                    if not can_move_permission:  # There's no permission to move the item.
                        failed.append(item)
                    else:  # There's permission, move the item.
                        succeeded.append(item)
                        item.workgroup = None
                        item.stewardship_organisation = new_stewardship_org
                        item.save()

            failed = list(set(failed))
            success = list(set(succeeded))
            failed_items = sorted([str(i.id) for i in failed])

            return self.generate_moving_message(new_stewardship_org.name, len(success), failed_items=failed_items)

    @classmethod
    def can_user(cls, user):
        return user_can_move_any_stewardship_organisation(user)


class DownloadActionForm(BulkActionForm):
    def make_changes(self):
        from aristotle_mdr.contrib.redirect.exceptions import Redirect
        items = self.items_to_change
        get_params = '?' + '&'.join(['items=%s' % i.id for i in items])
        url = reverse('aristotle:download_options', kwargs={'download_type': self.download_type}) + get_params
        raise Redirect(url=url)


class QuickPDFDownloadForm(DownloadActionForm):
    classes = "fa-file-pdf-o"
    action_text = _('Quick PDF download')
    items_label = "Items that are downloaded"
    download_type = 'pdf'
    title = None


class BulkDownloadForm(DownloadActionForm):
    confirm_page = "aristotle_mdr/actions/bulk_actions/bulk_download.html"
    classes = "fa-download"
    action_text = _('Bulk download')
    items_label = "These are the items that will be downloaded"

    download_type = forms.ChoiceField(
        choices=[],
        widget=forms.RadioSelect
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['download_type'] = forms.ChoiceField(
            choices=[
                (d_type.download_type, d_type.label)
                for d_type in fetch_aristotle_downloaders()
            ],
            widget=forms.RadioSelect
        )
        self.fields['items'].required = True

    def make_changes(self):
        self.download_type = self.cleaned_data['download_type']
        super().make_changes()
