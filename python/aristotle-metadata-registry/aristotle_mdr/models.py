import uuid
import reversion  # import revisions
from typing import List, Union, Optional, Dict
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.db import models, transaction
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType

from model_utils import Choices, FieldTracker
from model_utils.models import TimeStampedModel
from aristotle_mdr.contrib.async_signals.utils import fire
from aristotle_mdr.utils.model_utils import (
    baseAristotleObject,
    ManagedItem,
    aristotleComponent,
    discussionAbstract,
    AbstractValue,
    DedBaseThrough,
    unmanagedObject,
    get_comet_indicator_relational_attributes,
)
from ckeditor_uploader.fields import RichTextUploadingField as RichTextField
from aristotle_mdr import perms
from aristotle_mdr.utils import (
    fetch_aristotle_settings,
    fetch_metadata_apps,
    url_slugify_concept,
    url_slugify_workgroup,
    url_slugify_registration_authoritity,
    url_slugify_organization,
    strip_tags,
)
from aristotle_mdr.utils.text import truncate_words

from jsonfield import JSONField
from .fields import (
    ConceptForeignKey,
    ConceptManyToManyField,
    ConvertedConstrainedImageField,
    ConceptGenericRelation
)

from .managers import (
    ConceptManager,
    WorkgroupQuerySet,
    StewardOrganisationQuerySet,
    RegistrationAuthorityQuerySet,
    StatusQuerySet,
    SupersedesManager,
    ProposedSupersedesManager
)

from aristotle_mdr.contrib.groups.base import (
    AbstractGroup,
    AbstractMembership,
)

import logging

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)

"""
This is the core modelling for Aristotle mapping ISO/IEC 11179 classes to Python classes/Django models.

Docstrings are copied directly from the ISO/IEC 11179-3 documentation in their original form.
References to the originals is kept where possible using brackets and the dotted section numbers -
Eg. explanatory_comment (8.1.2.2.3.4)
"""

# 11179 States
# When used these MUST be used as IntegerFields to allow status comparison
STATES = Choices(
    (0, 'notprogressed', _('Not Progressed')),
    (1, 'incomplete', _('Incomplete')),
    (2, 'candidate', _('Candidate')),
    (3, 'recorded', _('Recorded')),
    (4, 'qualified', _('Qualified')),
    (5, 'standard', _('Standard')),
    (6, 'preferred', _('Preferred Standard')),
    (7, 'superseded', _('Superseded')),
    (8, 'retired', _('Retired')),
)

VERY_RECENTLY_SECONDS = 15

concept_visibility_updated = Signal(providing_args=["concept"])


class StewardOrganisation(AbstractGroup):
    objects = StewardOrganisationQuerySet.as_manager()

    class Meta:
        verbose_name = "Steward Organisation"

    roles = Choices(
        ('admin', _('Admin')),
        ('steward', _('Steward')),
        ('member', _('Member')),
    )
    owner_roles = [roles.admin]
    new_member_role = roles.member

    class Permissions:
        @classmethod
        def can_view_group(cls, user, group=None):
            if group.state in group.visible_states:
                return True

            if user.is_superuser:
                return True

            if group.state == group.states.private:
                return AbstractGroup.Permissions.is_member(user, group)

            if group.state == group.states.hidden:
                return user.is_superuser

            return False

    role_permissions = {
        "view_group": [Permissions.can_view_group],
        "manage_workgroups": [roles.admin],
        "publish_objects": [roles.admin, roles.steward],
        "manage_regstration_authorities": [roles.admin],
        "edit_group_details": [roles.admin],
        "edit_members": [roles.admin],
        "invite_member": [roles.admin],
        "manage_managed_items": [roles.admin, roles.steward],
        "manage_collections": [roles.admin, roles.steward],
        "list_workgroups": [roles.admin, AbstractGroup.Permissions.is_member],
        "manage_references": [roles.admin, roles.steward],
    }
    states = Choices(
        ('active', _('Active')),
        ('private', _('Private')),
        ('archived', _('Deactivated & Visible')),
        ('hidden', _('Deactivated & Hidden')),
    )

    active_states = [
        states.active,
        states.private,
    ]
    visible_states = [
        states.active, states.archived,
    ]

    description = RichTextField(
        _('definition'),
        help_text=_("Representation of a concept by a descriptive statement "
                    "which serves to differentiate it from related concepts. (3.2.39)")
    )

    def get_absolute_url(self):
        return reverse(
            "aristotle_mdr:stewards:group:detail",
            args=[self.slug]
        )


class StewardOrganisationMembership(AbstractMembership):
    group_class = StewardOrganisation
    group_kwargs = {"to_field": "uuid"}


class registryGroup(unmanagedObject):
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="%(class)s_manager_in",
        verbose_name=_('Managers')
    )

    class Meta:
        abstract = True

    def can_edit(self, user):
        return user.is_superuser or self.managers.filter(pk=user.pk).exists()

    @property
    def help_name(self):
        return self._meta.model_name

    def list_roles_for_user(self, user):
        # This should always be overridden
        raise NotImplementedError  # pragma: no cover


class Organization(registryGroup):
    """
    6.3.6 - Organization is a class each instance of which models an organization (3.2.90),
    a unique framework of authority within which individuals (3.2.65) act, or are designated to act,
    towards some purpose.
    """
    template = "aristotle_mdr/organization/organization.html"
    uri = models.URLField(  # 6.3.6.2.5
        blank=True, null=True,
        help_text="uri for Organization"
    )

    def promote_to_registration_authority(self):
        ra = RegistrationAuthority(organization_ptr=self)
        ra.save()
        return ra

    def get_absolute_url(self):
        return url_slugify_organization(self)


class OrganizationRecord(ManagedItem):
    """A record of an organization"""


RA_ACTIVE_CHOICES = Choices(
    (0, 'active', _('Active & Visible')),
    (1, 'inactive', _('Inactive & Visible')),
    (2, 'hidden', _('Inactive & Hidden'))
)


class RegistrationAuthority(Organization):
    """
    8.1.2.5 - Registration_Authority class

    Registration_Authority is a class each instance of which models a registration authority (3.2.109),
    an organization (3.2.90) responsible for maintaining a register (3.2.104).

    A registration authority may register many administered items (3.2.2) as shown by the Registration
    (8.1.5.1) association class.
    """
    objects = RegistrationAuthorityQuerySet.as_manager()
    stewardship_organisation = models.ForeignKey(StewardOrganisation, to_field="uuid", on_delete=models.CASCADE)
    template = "aristotle_mdr/organization/registration_authority/home.html"

    active = models.IntegerField(
        choices=RA_ACTIVE_CHOICES,
        default=RA_ACTIVE_CHOICES.active,
        help_text=_('Setting this to Inactive will disable all further registration actions')
    )
    locked_state = models.IntegerField(
        choices=STATES,
        help_text=_(
            "When metadata is endorsed at  the specified 'locked' level, the metadata item will not longer be able to be altered by standard users. Only Workgroup or Organisation Stewards will be able to edit 'locked' metadata."),
        default=STATES.candidate
    )
    public_state = models.IntegerField(
        choices=STATES,
        help_text=_(
            "When metadata is endorsed at the specified 'public' level, the metadata item will be visible to all users"),
        default=STATES.recorded
    )

    registrars = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='registrar_in',
        verbose_name=_('Registrars')
    )

    # The below text fields allow for brief descriptions of the context of each
    # state for a particular Registration Authority
    # For example:
    # For a particular Registration Authority standard may mean"
    #   "Approved by a simple majority of the standing council of metadata
    #    standardisation"
    # While "Preferred Standard" may mean:
    #   "Approved by a two-thirds majority of the standing council of metadata
    #    standardisation"

    notprogressed = models.TextField(
        _("Not Progressed"),
        help_text=_(
            "A description of the meaning of the 'Not Progressed' status level for this Registration Authority."),
        blank=True
    )
    incomplete = models.TextField(
        _("Incomplete"),
        help_text=_("A description of the meaning of the 'Incomplete' status level for this Registration Authority."),
        blank=True
    )
    candidate = models.TextField(
        _("Candidate"),
        help_text=_("A description of the meaning of the 'Candidate' status level for this Registration Authority."),
        blank=True
    )
    recorded = models.TextField(
        _("Recorded"),
        help_text=_("A description of the meaning of the 'Recorded' status level for this Registration Authority."),
        blank=True
    )
    qualified = models.TextField(
        _("Qualified"),
        help_text=_("A description of the meaning of the 'Qualified' status level for this Registration Authority."),
        blank=True
    )
    standard = models.TextField(
        _("Standard"),
        help_text=_("A description of the meaning of the 'Standard' status level for this Registration Authority."),
        blank=True
    )
    preferred = models.TextField(
        _("Preferred Standard"),
        help_text=_(
            "A description of the meaning of the 'Preferred Standard' status level for this Registration Authority."),
        blank=True
    )
    superseded = models.TextField(
        _("Superseded"),
        help_text=_("A description of the meaning of the 'Superseded' status level for this Registration Authority."),
        blank=True
    )
    retired = models.TextField(
        _("Retired"),
        help_text=_("A description of the meaning of the 'Retired' status level for this Registration Authority."),
        blank=True
    )

    tracker = FieldTracker()

    class Meta:
        verbose_name_plural = _("Registration Authorities")

    roles = {
        'registrar': _("Registrar"),
        'manager': _("Manager")
    }

    @property
    def unlocked_states(self):
        return range(STATES.notprogressed, self.locked_state)

    @property
    def locked_states(self):
        return range(self.locked_state, self.public_state)

    @property
    def public_states(self):
        return range(self.public_state, STATES.retired + 1)

    @property
    def members(self):
        from django.contrib.auth import get_user_model
        um = get_user_model()

        reg_pks = list(self.registrars.all().values_list("pk", flat=True))
        man_pks = list(self.managers.all().values_list("pk", flat=True))

        pks = set(reg_pks + man_pks)
        return um.objects.filter(pk__in=pks)

    @property
    def is_active(self):
        return self.active == RA_ACTIVE_CHOICES.active

    @property
    def is_visible(self):
        return not self.active == RA_ACTIVE_CHOICES.hidden

    @property
    def short_definition(self):
        stripped = strip_tags(self.definition)
        return truncate_words(stripped, 50)

    def get_absolute_url(self):
        return url_slugify_registration_authoritity(self)

    def can_view(self, user):
        return True

    def statusDescriptions(self):
        descriptions = [
            self.notprogressed,
            self.incomplete,
            self.candidate,
            self.recorded,
            self.qualified,
            self.standard,
            self.preferred,
            self.superseded,
            self.retired
        ]

        unlocked = [
            (i, STATES[i], descriptions[i]) for i in self.unlocked_states
        ]
        locked = [
            (i, STATES[i], descriptions[i]) for i in self.locked_states
        ]
        public = [
            (i, STATES[i], descriptions[i]) for i in self.public_states
        ]

        return (
            ('unlocked', unlocked),
            ('locked', locked),
            ('public', public)
        )

    def cascaded_register(self, item, state, user, *args, **kwargs):
        """
        Register an item and all it's sub components. If the user has permission
        """
        if not perms.user_can_add_ra_status(user, self, item):
            # Return a failure as this item isn't allowed
            return {'success': [], 'failed': [item] + item.registry_cascade_items}

        revision_message = _(
            "Cascade registration of item '%(name)s' (id:%(iid)s)\n"
        ) % {'name': item.name,
             'iid': item.id}

        revision_message = revision_message + kwargs.get('changeDetails', "")
        seen_items = {'success': [], 'failed': []}

        with transaction.atomic(), reversion.revisions.create_revision():
            reversion.revisions.set_user(user)
            reversion.revisions.set_comment(revision_message)

            all_items = [item] + item.registry_cascade_items

            for child_item in all_items:
                if perms.user_can_add_ra_status(user, self, child_item):
                    self._register(
                        child_item, state, user, *args, **kwargs
                    )
                    seen_items['success'].append(child_item)
                else:
                    seen_items['failed'].append(child_item)
        return seen_items

    def register(self, item, state, user, *args, **kwargs):
        """
        Register an item. If the user has permission
        """
        if not perms.user_can_add_ra_status(user, self, item):
            # Return a failure as this item isn't allowed
            return {'success': [], 'failed': [item]}

        revision_message = kwargs.get('changeDetails', "")
        with transaction.atomic(), reversion.revisions.create_revision():
            reversion.revisions.set_user(user)
            reversion.revisions.set_comment(revision_message)
            self._register(item, state, user, *args, **kwargs)

        return {'success': [item], 'failed': []}

    def _register(self, item, state, user, *args, **kwargs):
        """
        Internal function that performs actual registration
        Does not do any permissions checks
        Used by register and cascaded_register functions
        """
        if self.active is RA_ACTIVE_CHOICES.active:
            changeDetails = kwargs.get('changeDetails', "")
            # If registrationDate is None (like from a form), override it with
            # todays date.
            registrationDate = kwargs.get('registrationDate', None) or timezone.now().date()
            until_date = kwargs.get('until_date', None)

            Status.objects.create(
                concept=item,
                registrationAuthority=self,
                registrationDate=registrationDate,
                state=state,
                changeDetails=changeDetails,
                until_date=until_date
            )

    def list_roles_for_user(self, user):
        roles = []
        if user in self.managers.all():
            roles.append("manager")
        if user in self.registrars.all():
            roles.append("registrar")
        return roles

    def giveRoleToUser(self, role, user):
        if role == 'registrar':
            self.registrars.add(user)
        if role == "manager":
            self.managers.add(user)

    def removeRoleFromUser(self, role, user):
        if role == 'registrar':
            self.registrars.remove(user)
        if role == "manager":
            self.managers.remove(user)

    def removeUser(self, user):
        self.registrars.remove(user)
        self.managers.remove(user)


@receiver(post_save, sender=RegistrationAuthority)
def update_registration_authority_states(sender, instance, created, **kwargs):
    if not created:
        if instance.tracker.has_changed('public_state') \
                or instance.tracker.has_changed('locked_state'):
            message = (
                "Registration '{ra}' changed its public or locked status "
                "level, items registered by this authority may have stale "
                "visiblity states and need to be manually updated."
            ).format(ra=instance.name)


class Workgroup(AbstractGroup, TimeStampedModel):
    """
    A workgroup is a collection of associated users given control to work on a
    specific piece of work. Usually this work will be the creation of a
    specific collection of objects, such as data elements, for a specific
    topic.

    Workgroup owners may choose to 'archive' a workgroup. All content remains
    visible, but the workgroup is hidden in lists and new items cannot be
    created in that workgroup.
    """
    template = "aristotle_mdr/workgroup.html"
    can_invite_new_users_via_email = False
    objects = WorkgroupQuerySet.as_manager()
    stewardship_organisation = models.ForeignKey(StewardOrganisation, to_field="uuid", on_delete=models.CASCADE)
    archived = models.BooleanField(
        default=False,
        help_text=_("Archived workgroups can no longer have new items or "
                    "discussions created within them."),
        verbose_name=_('Archived'),
    )

    class Permissions:
        @classmethod
        def can_view_group(cls, user, group=None):
            return group.state in group.active_states and cls.is_member(user, group)

    roles = Choices(
        ('manager', _('Manager')),
        ('steward', _('Steward')),
        ('submitter', _('Submitter')),
        ('viewer', _('Viewer')),
    )
    owner_roles = [roles.manager]
    new_member_role = roles.viewer

    role_permissions = {
        "view_group": [Permissions.can_view_group],
        "edit_group_details": [roles.manager],
        "edit_members": [roles.manager],
        "invite_member": [roles.manager],
    }
    states = Choices(
        ('active', _('Active')),
        ('archived', _('Deactivated & Visible')),
        ('hidden', _('Deactivated & Hidden')),
    )

    active_states = [
        states.active,
    ]
    visible_states = [
        states.active, states.archived,
    ]

    definition = RichTextField(
        _('definition'),
        null=True, blank=True,
        help_text=_("Representation of a concept by a descriptive statement "
                    "which serves to differentiate it from related concepts. (3.2.39)")
    )

    tracker = FieldTracker()

    def get_absolute_url(self):
        return url_slugify_workgroup(self)

    def can_view(self, user):
        # If the user has permission to manage workgroups within the stewardship organisation the work-group
        # is a part of
        if self.stewardship_organisation.user_has_permission(user, "manage_workgroups"):
            return True
        return self.member_list.filter(pk=user.pk).exists()

    @property
    def classedItems(self):
        # Convenience class as we can't call functions in templates
        return self.items.select_subclasses()

    def list_roles_for_user(self, user):
        return self.roles_for_user(user)

    def giveRoleToUser(self, role, user):
        if role == "manager":
            self.grant_role(self.roles.manager, user)
        if role == "viewer":
            self.grant_role(self.roles.viewer, user)
        if role == "submitter":
            self.grant_role(self.roles.submitter, user)
        if role == "steward":
            self.grant_role(self.roles.steward, user)
        self.save()

    def removeRoleFromUser(self, role, user):
        if role == "manager":
            self.revoke_role(self.roles.manager, user)
        if role == "viewer":
            self.revoke_role(self.roles.viewer, user)
        if role == "submitter":
            self.revoke_role(self.roles.submitter, user)
        if role == "steward":
            self.revoke_role(self.roles.steward, user)
        self.save()

    def removeUser(self, user):
        self.revoke_membership(user)

    def can_edit(self, user):
        return user.is_superuser or self.has_role('manager', user.pk)


class WorkgroupMembership(AbstractMembership):
    group_class = Workgroup
    group_kwargs = {"to_field": "uuid"}


class DiscussionPost(discussionAbstract):
    workgroup = models.ForeignKey(Workgroup, related_name='discussions', on_delete=models.CASCADE)
    title = models.CharField(max_length=256)
    relatedItems = models.ManyToManyField(
        '_concept',
        blank=True,
        related_name='relatedDiscussions',
    )
    closed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-modified']

    @property
    def active(self):
        return not self.closed

    def get_absolute_url(self):
        return reverse(
            "aristotle:discussionsPost",
            args=[self.pk]
        )

    def __str__(self):
        return self.title


class DiscussionComment(discussionAbstract):
    post = models.ForeignKey(DiscussionPost, related_name='comments', on_delete=models.CASCADE)

    class Meta:
        ordering = ['created']

    def get_absolute_url(self):
        return self.post.get_absolute_url() + '/#comment_' + str(self.id)

    def __str__(self):
        return self.body


class _concept(baseAristotleObject):
    """
    9.1.2.1 - Concept class
    Concept is a class each instance of which models a concept (3.2.18),
    a unit of knowledge created by a unique combination of characteristics (3.2.14).
    A concept is independent of representation.

    This is the base concrete class that ``Status`` items attach to, and to
    which collection objects refer to. It is not marked abstract in the Django
    Meta class, and **must not be inherited from**. It has relatively few
    fields and is a convenience class to link with in relationships.
    """
    objects = ConceptManager()
    template = "aristotle_mdr/concepts/managedContent.html"
    list_details_template = "aristotle_mdr/helpers/concept_list_details.html"
    stewardship_organisation = models.ForeignKey(
        StewardOrganisation, to_field="uuid",
        null=True, blank=True,
        related_name="metadata",
        on_delete=models.CASCADE
    )

    publication_details = ConceptGenericRelation('aristotle_mdr_publishing.PublicationRecord')
    version_publication_details = GenericRelation('aristotle_mdr_publishing.VersionPublicationRecord')

    workgroup = models.ForeignKey(Workgroup, related_name="items", null=True, blank=True, on_delete=models.SET_NULL)
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="created_items",
        null=True, blank=True,
        help_text=_('This is the person who first created an item. Users can always see items they made.'),
        on_delete=models.PROTECT
    )
    # We will query on these, so want them cached with the items themselves
    # To be usable these must be updated when statuses are changed
    _is_public = models.BooleanField(default=False)
    _is_locked = models.BooleanField(default=False)

    # Cache of what type of item this is (set in handle_object_save)
    _type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    version = models.CharField(max_length=20, blank=True)
    references = RichTextField(blank=True)
    origin_URI = models.URLField(
        blank=True,
        help_text=_("If imported, the original location of the item")
    )
    origin = RichTextField(
        help_text=_("The source (e.g. document, project, discipline or model) for the item (8.1.2.2.3.5)"),
        blank=True
    )
    comments = RichTextField(
        help_text=_("Descriptive comments about the metadata item (8.1.2.2.3.4)"),
        blank=True
    )

    superseded_by_items = ConceptManyToManyField(  # 11.5.3.4
        'self',
        through='SupersedeRelationship',
        related_name="superseded_items",
        # blank=True,
        through_fields=('older_item', 'newer_item'),
        symmetrical=False,
        # help_text=_("")
    )

    tracker = FieldTracker()

    edit_page_excludes: List[str] = []
    admin_page_excludes: List[str] = []
    # List of fields that will only be displayed if 'aristotle_backwards' is
    # enabled
    backwards_compatible_fields: List[str] = []
    registerable = True
    relational_attributes: Dict[str, Dict] = {}
    # Used by concept manager with_related in a select_related
    related_objects: List[str] = []
    # Fields to build the name from
    name_suggest_fields: List[str] = []

    class Meta:
        # So the url_name works for items we can't determine.
        verbose_name = "item"
        indexes = [
            models.Index(fields=['uuid']),
        ]

    class ReportBuilder:
        exclude = ('_is_public', '_is_locked', '_type')

    @classmethod
    def model_to_publish(cls):
        return _concept

    @classmethod
    def custom_help(cls):
        from aristotle_mdr.utils import cloud_enabled
        if not cloud_enabled():
            return None
        ct = ContentType.objects.get_for_model(cls)
        return ct.custom_help

    @property
    def non_cached_fields_changed(self):
        changed = self.tracker.changed()
        changed.pop('_is_public', False)
        changed.pop('_is_locked', False)
        changed.pop('_type', False)
        return len(changed.keys()) > 0

    @property
    def changed_fields(self):
        # changed = self.tracker.changed()
        # changed.pop('_is_public', False)
        # changed.pop('_is_locked', False)
        return self.tracker.changed()

    @property
    def cached_item(self) -> Optional[models.Model]:
        """
        Return cached subclassed item or None
        The .item property below should be used instead
        unless the slow query needs to be avoided in all cases
        """
        item = None
        ct = self._type
        if ct is not None:
            model = ct.model_class()
            try:
                item = model.objects.get(pk=self.pk)
            except model.DoesNotExist:
                # This should never happen if _type wasn't messed with
                return None

        return item

    @property
    def item(self) -> models.Model:
        """
        Performs a lookup to find the subclassed item.
        If the type is cached in _type this lookup is fast
        otherwise InheritanceManager is used which is quite slow
        """
        cached_item = self.cached_item
        if cached_item is not None:
            return cached_item

        # Fallback to using get_subclass (this is slow)
        item = _concept.objects.get_subclass(pk=self.pk)
        # Set _type for future calls (dont save though)
        self._type = ContentType.objects.get_for_model(type(item))

        return item

    @property
    def item_type(self) -> ContentType:
        """
        Returns the content type of the subclassed item
        e.g. "object class"
        """
        if self._type_id:
            # Use get_for_id so the internal cache is used
            return ContentType.objects.get_for_id(self._type_id)

        # Fallback to using get_subclass (this is slow)
        instance = _concept.objects.get_subclass(pk=self.pk)
        model = type(instance)
        ct = ContentType.objects.get_for_model(type(instance))
        # Set _type for future calls (dont save though)
        self._type = ct

        return ct

    @property
    def item_type_name(self) -> str:
        """
        Returns the verbose name of the subclassed items type
        e.g. "Object Class"
        """
        # Get content type
        ct = self.item_type
        # Get model and return name
        model = ct.model_class()
        return model.get_verbose_name()

    @property
    def concept(self):
        """
        Returns the parent _concept that an item is built on.
        If the item type is _concept, return itself.
        """
        return getattr(self, '_concept_ptr', self)

    @property
    def short_definition(self):
        """
        Provides a truncated (20 characters long) description of the item.
        Html tags are stripped.
        :return: 20 character long string.
        """
        stripped = strip_tags(self.definition)
        return truncate_words(stripped, 20)

    @property
    def submitting_organizations(self):
        return self.org_records.all().filter(type='s')

    @property
    def responsible_organizations(self):
        return self.org_records.all().filter(type='r')

    @classmethod
    def get_autocomplete_name(cls):
        return 'Autocomplete' + "".join(
            cls._meta.verbose_name.title().split()
        )

    @staticmethod
    def autocomplete_search_fields(self):
        return ("name__icontains",)

    def get_absolute_url(self):
        return url_slugify_concept(self)

    @property
    def registry_cascade_items(self) -> List:
        """
        This returns the items that can be registered along with the this item.
        If a subclass of _concept defines this method, then when an instance
        of that class is registered using a cascading method then that
        instance, all instances returned by this method will all recieve the
        same registration status.

        Reimplementations of this MUST return lists of concept subclasses.
        """
        return []

    @property
    def is_registered(self):
        return self.statuses.count() > 0

    @property
    def is_superseded(self):
        return self.statuses.filter(state=STATES.superseded).count() > 0 and all(
            STATES.superseded == status.state for status in self.statuses.all()
        ) and self.superseded_by_items_relation_set.count() > 0

    @property
    def is_retired(self):
        return all(
            STATES.retired == status.state for status in self.statuses.all()
        ) and self.statuses.count() > 0

    @property
    def favourited_by(self):
        from django.contrib.auth import get_user_model
        user_model = get_user_model()
        return user_model.objects.filter(
            profile__tags__favourites__item=self
        ).distinct()

    @property
    def editable_by(self):
        """Returns a list of the users allowed to edit this concept."""
        from django.contrib.auth import get_user_model
        query = (
            Q(
                Q(workgroupmembership__role__in=['submitter', 'steward', 'manager']) &
                Q(workgroupmembership__group=self.workgroup)
            ) |
            Q(created_items=self)
        )
        return get_user_model().objects.filter(query).distinct()

    @property
    def component_fields(self):
        return [
            field
            for field in type(self)._meta.get_fields()
            if field.is_relation and field.one_to_many and issubclass(field.related_model, aristotleComponent)
        ]

    @property
    def approved_supersedes(self):
        supersedes = self.superseded_items_relation_set.filter(proposed=False).select_related('older_item')
        return [ss.older_item for ss in supersedes]

    @property
    def approved_superseded_by(self):
        supersedes = self.superseded_by_items_relation_set.filter(proposed=False).select_related('newer_item')
        return [ss.newer_item for ss in supersedes]

    def can_edit(self, user):
        return _concept.objects.filter(pk=self.pk).editable(user).exists()

    def can_view(self, user):
        return _concept.objects.filter(pk=self.pk).visible(user).exists()

    def check_is_public(self, when=timezone.now()):
        """
        A concept is public if any registration authority
        has advanced it to a public state in that RA.
        """
        statuses = self.statuses.all()
        statuses = self.current_statuses(qs=statuses, when=when)
        pub_state = True in [
            s.state >= s.registrationAuthority.public_state for s in statuses
        ]

        q = Q()
        extra = False
        extra_q = fetch_aristotle_settings().get('EXTRA_CONCEPT_QUERYSETS', {}).get('public', None)
        if extra_q:
            for func in extra_q:
                q |= import_string(func)()
            extra = self.__class__.objects.filter(pk=self.pk).filter(q).exists()
        return pub_state or extra

    def is_public(self):
        return self._is_public

    is_public.boolean = True  # type: ignore
    is_public.short_description = 'Public'  # type: ignore

    def check_is_locked(self, when=timezone.now()):
        """
        A concept is locked if any registration authority
        has advanced it to a locked state in that RA.
        """
        statuses = self.statuses.all()
        statuses = self.current_statuses(qs=statuses, when=when)
        return True in [
            s.state >= s.registrationAuthority.locked_state for s in statuses
        ]

    def is_locked(self):
        return self._is_locked

    is_locked.boolean = True  # type: ignore
    is_locked.short_description = 'Locked'  # type: ignore

    def recache_states(self):
        self._is_public = self.check_is_public()
        self._is_locked = self.check_is_locked()
        self.save()
        concept_visibility_updated.send(sender=self.__class__, concept=self)

    def current_statuses(self, qs=None, when=timezone.now()):
        if qs is None:
            qs = self.statuses.all()

        return qs.current(when)

    def get_download_items(self) -> List[Union[models.Model, QuerySet]]:
        """
        When downloading a concept, extra items can be included for download by
        overriding the ``get_download_items`` method on your item. By default
        this returns an empty list, but can be modified to include any number of
        items that inherit from ``_concept``.

        When overriding, each entry in the list can be either an item or a queryset
        """
        return []


class concept(_concept):
    """
    This is an abstract class that all items that should behave like a 11179
    Concept **must inherit from**. This model includes the definitions for many
    long and optional text fields and the self-referential ``superseded_by``
    field. It is not possible to include this model in a ``ForeignKey`` or
    ``ManyToManyField``.
    """
    objects = ConceptManager()

    class Meta:
        abstract = True

    @property
    def help_name(self):
        return self._meta.model_name

    @property
    def item(self):
        """
        Return self, because we already have the correct item.
        """
        return self


class SupersedeRelationship(TimeStampedModel):
    # Whether this relationship is proposed by a review,
    # or an actual approved relation
    proposed = models.BooleanField(
        default=False,
        help_text='Whether this is a proposal or an active supersedes relation'
    )
    older_item = ConceptForeignKey(
        _concept,
        related_name='superseded_by_items_relation_set',
        on_delete=models.CASCADE
    )
    newer_item = ConceptForeignKey(
        _concept,
        related_name='superseded_items_relation_set',
        on_delete=models.CASCADE
    )
    registration_authority = models.ForeignKey(RegistrationAuthority, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    date_effective = models.DateField(
        _('Date effective'),
        help_text=_("The date the superseding relationship became effective."),
        blank=True, null=True
    )
    review = ConceptForeignKey(
        'aristotle_mdr_review_requests.ReviewRequest',
        null=True,
        default=None,
        related_name='supersedes',
        on_delete=models.SET_NULL
    )

    objects = models.Manager()
    approved = SupersedesManager()  # Only non proposed relationships can be retrieved here
    proposed_objects = ProposedSupersedesManager()  # Only proposed objects can be retrieved here


class RecordRelation(TimeStampedModel):
    """Link between a concept and an organization record"""
    TYPE_CHOICES = Choices(
        ('s', 'Submitting Organization'),
        ('r', 'Responsible Organization'),
    )

    concept = ConceptForeignKey(_concept, related_name='org_records', on_delete=models.CASCADE)
    organization_record = models.ForeignKey(OrganizationRecord, on_delete=models.PROTECT)
    type = models.CharField(
        choices=TYPE_CHOICES,
        max_length=1,
    )


REVIEW_STATES = Choices(
    (0, 'submitted', _('Submitted')),
    (5, 'cancelled', _('Cancelled')),
    (10, 'accepted', _('Accepted')),
    (15, 'rejected', _('Rejected')),
)


class Status(TimeStampedModel):
    """
    8.1.2.6 - Registration_State class
    A Registration_State is a collection of information about the Registration (8.1.5.1) of an Administered Item (8.1.2.2).
    The attributes of the Registration_State class are summarized here and specified more formally in 8.1.2.6.2.
    """
    objects = StatusQuerySet.as_manager()
    concept = ConceptForeignKey(_concept, related_name="statuses", on_delete=models.CASCADE)
    registrationAuthority = models.ForeignKey(RegistrationAuthority, on_delete=models.CASCADE)
    changeDetails = models.TextField(
        _("Change details"),
        blank=True,
        null=True
    )
    state = models.IntegerField(
        _("State"),
        choices=STATES,
        default=STATES.incomplete,
        help_text=_("Designation (3.2.51) of the status in the registration life-cycle of an Administered_Item")
    )
    # TODO: Below should be changed to 'effective_date' to match ISO IEC
    # 11179-6 (Section 8.1.2.6.2.2)
    registrationDate = models.DateField(
        _('Date registration effective'),
        help_text=_("Date and time an Administered_Item became/becomes available to registry users.")
    )
    until_date = models.DateField(
        _('Date registration expires'),
        blank=True,
        null=True,
        help_text=_(
            "Date and time the Registration of an Administered_Item by a Registration_Authority in a registry is no longer effective."
        )
    )
    tracker = FieldTracker()

    class Meta:
        verbose_name_plural = "Statuses"

    @property
    def state_name(self):
        return STATES[self.state]

    def __str__(self):
        return "{obj} is {stat} for {ra} on {date} - {desc}".format(
            obj=self.concept.name,
            stat=self.state_name,
            ra=self.registrationAuthority,
            desc=self.changeDetails,
            date=self.registrationDate
        )


def recache_concept_states(sender, instance, *args, **kwargs):
    instance.concept.recache_states()


post_save.connect(recache_concept_states, sender=Status)
post_delete.connect(recache_concept_states, sender=Status)


class ObjectClass(concept):
    """
    Set of ideas, abstractions or things in the real world that are
    identified with explicit boundaries and meaning and whose properties and
    behaviour follow the same rules (3.2.88)
    """
    template = "aristotle_mdr/concepts/objectClass.html"

    class Meta:
        verbose_name_plural = "Object Classes"

    @property
    def relational_attributes(self):
        rels = {
            "data_element_concepts": {
                "all": _("Data Element Concepts implementing this Object Class"),
                "qs": self.dataelementconcept_set.all()
            },
        }
        if "aristotle_ontology" in fetch_aristotle_settings().get('CONTENT_EXTENSIONS'):
            from aristotle_ontology.models import ObjectClassSpecialisation
            rels.update({
                'broader_specialisations': {
                    "all": _("As a broader class of"),
                    "qs": self.oc_as_broader.all()
                },
                'narrower_specialisations': {
                    "all": _("As a specialisation class of"),
                    "qs": ObjectClassSpecialisation.objects.filter(
                        objectclassspecialisationnarrowerclass__narrower_class=self
                    ).all()
                },
            })
        return rels


class Property(concept):
    """
    Quality common to all members of an :model:`aristotle_mdr.ObjectClass`
    (3.2.100)
    """
    template = "aristotle_mdr/concepts/property.html"

    class Meta:
        verbose_name_plural = "Properties"

    @property
    def relational_attributes(self):
        rels = {
            "data_element_concepts": {
                "all": _("Data Element Concepts implementing this Property"),
                "qs": self.dataelementconcept_set.all()
            },
        }
        return rels


class Measure(ManagedItem):
    """
    Measure_Class is a class each instance of which models a measure class (3.2.72),
    a set of equivalent units of measure (3.2.138) that may be shared across multiple
    dimensionalities (3.2.58). Measure_Class allows a grouping of units of measure to
    be specified once, and reused by multiple dimensionalities.

    NB. A measure is not defined as a concept in ISO 11179 (11.4.2.2)
    """
    template = "aristotle_mdr/manageditems/measure.html"


class UnitOfMeasure(concept):
    """
    actual units in which the associated values are measured
    :model:`aristotle_mdr.ValueDomain` (3.2.138)
    """

    class Meta:
        verbose_name_plural = "Units Of Measure"

    template = "aristotle_mdr/concepts/unitOfMeasure.html"
    list_details_template = "aristotle_mdr/concepts/list_details/unit_of_measure.html"
    measure = models.ForeignKey(
        Measure,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    symbol = models.CharField(max_length=20, blank=True)

    @property
    def relational_attributes(self):
        return {
            "value_domains": {
                "all": _("Value Domains implementing this Unit of Measure"),
                "qs": self.valuedomain_set.all()
            },
        }


class DataType(concept):
    """
    set of distinct values, characterized by properties of those values and
    by operations on those values (3.1.9)
    """
    template = "aristotle_mdr/concepts/dataType.html"

    @property
    def relational_attributes(self):
        return {
            "value_domains": {
                "all": _("Value Domains implementing this Data Type"),
                "qs": self.valuedomain_set.all()
            },
        }


class ConceptualDomain(concept):
    """
    Concept that expresses its description or valid instance meanings (3.2.21)
    """

    # Implementation note: Since a Conceptual domain "must be either one or
    # both an Enumerated Conceptual or a Described_Conceptual_Domain" there is
    # no reason to model them separately.

    template = "aristotle_mdr/concepts/conceptualDomain.html"
    description = RichTextField(
        _('Description'),
        blank=True,
        help_text=_(
            ('Description or specification of a rule, reference, or '
             'range for a set of all value meanings for a Conceptual Domain')
        )
    )
    serialize_weak_entities = [
        ('value_meaning', 'valuemeaning_set'),
    ]

    @property
    def relational_attributes(self):
        return {
            "data_element_concepts": {
                "all": _("Data Element Concepts implementing this Conceptual Domain"),
                "qs": self.dataelementconcept_set.all()
            },
            "value_domains": {
                "all": _("Value Domains Concepts implementing this Conceptual Domain"),
                "qs": self.valuedomain_set.all()
            },
        }


class ValueMeaning(aristotleComponent):
    """
    Value_Meaning is a class each instance of which models a value meaning (3.2.141),
    which provides semantic content of a possible value (11.3.2.3.2).
    """

    class Meta:
        ordering = ['order']

    name = models.CharField(  # 3.2.141
        max_length=255,
        help_text=_('The semantic content of a possible value (3.2.141)')
    )
    definition = models.TextField(
        null=True, blank=True,
        help_text=_('The semantic definition of a possible value')
    )
    conceptual_domain = ConceptForeignKey(
        ConceptualDomain,
        verbose_name='Conceptual Domain',
        on_delete=models.CASCADE
    )
    order = models.PositiveSmallIntegerField("Position")
    start_date = models.DateField(
        blank=True,
        null=True,
        help_text=_('Date at which the value meaning became valid')
    )
    end_date = models.DateField(
        blank=True,
        null=True,
        help_text=_('Date at which the value meaning ceased to be valid')
    )

    parent_field_name = 'conceptual_domain'

    def __str__(self):
        return "%s: %s - %s" % (
            self.conceptual_domain.name,
            self.name,
            self.definition
        )


class ValueDomain(concept):
    """
    Value_Domain is a class each instance of which models a value domain (3.2.140),
    a set of permissible values (3.2.96) (11.3.2.5).
    """

    # Implementation note: Since a Value domain "must be either one or
    # both an Enumerated Valued or a Described_Value_Domain" there is
    # no reason to model them separately.

    template = "aristotle_mdr/concepts/valueDomain.html"
    list_details_template = "aristotle_mdr/concepts/list_details/value_domain.html"
    serialize_weak_entities = [
        ('permissible_values', 'permissiblevalue_set'),
        ('supplementary_values', 'supplementaryvalue_set'),
    ]
    clone_fields = ('permissiblevalue_set', 'supplementaryvalue_set')
    backwards_compatible_fields = ['classification_scheme', 'representation_class']

    data_type = ConceptForeignKey(  # 11.3.2.5.2.1
        DataType,
        blank=True,
        null=True,
        help_text=_('Datatype used in a Value Domain'),
        verbose_name='Data Type',
        on_delete=models.SET_NULL,
    )
    format = models.CharField(  # 11.3.2.5.2.1
        max_length=100,
        blank=True,
        null=True,
        help_text=_('template for the structure of the presentation of the value(s)')
    )
    maximum_length = models.PositiveIntegerField(  # 11.3.2.5.2.3
        blank=True,
        null=True,
        help_text=_('maximum number of characters available to represent the Data Element value')
    )
    unit_of_measure = ConceptForeignKey(  # 11.3.2.5.2.3
        UnitOfMeasure,
        blank=True,
        null=True,
        help_text=_('Unit of Measure used in a Value Domain'),
        verbose_name='Unit Of Measure',
        on_delete=models.SET_NULL,
    )
    conceptual_domain = ConceptForeignKey(
        ConceptualDomain,
        blank=True,
        null=True,
        help_text=_('The Conceptual Domain that this Value Domain which provides representation.'),
        verbose_name='Conceptual Domain',
        on_delete=models.SET_NULL,
    )
    classification_scheme = ConceptForeignKey(
        'aristotle_mdr_backwards.ClassificationScheme',
        blank=True,
        null=True,
        related_name='valueDomains',
        verbose_name='Classification Scheme',
        on_delete=models.SET_NULL,
    )
    representation_class = ConceptForeignKey(
        'aristotle_mdr_backwards.RepresentationClass',
        blank=True,
        null=True,
        related_name='value_domains',
        verbose_name='Representation Class',
        on_delete=models.SET_NULL,
    )
    description = RichTextField(
        _('Description'),
        blank=True,
        help_text=('Description or specification of a rule, reference, or '
                   'range for a set of all values for a Value Domain.')
    )

    @property
    def permissibleValues(self):
        return self.permissiblevalue_set.all()

    @property
    def supplementaryValues(self):
        return self.supplementaryvalue_set.all()

    @property
    def relational_attributes(self):
        return {
            "data_elements": {
                "all": _("Data Elements implementing this Value Domain"),
                "qs": self.dataelement_set.all()
            },
        }


class PermissibleValue(AbstractValue):
    """
    Permissible Value is a class each instance of which models a permissible value (3.2.96),
    the designation (3.2.51) of a value meaning (3.2.141).
    """

    class Meta:
        ordering = ['order']
        verbose_name = "Permissible Value"


class SupplementaryValue(AbstractValue):
    class Meta:
        ordering = ['order']
        verbose_name = "Supplementary Value"


class DataElementConcept(concept):
    """
    Data Element Concept is a class each instance of which models a data element concept (3.2.29).
    A data element concept is a specification of a concept (3.2.18) independent of any particular representation.
    A data element concept can be represented in the form of a data element (3.2.28).

    Concept that is an association of a :model:`aristotle_mdr.Property`
    with an :model:`aristotle_mdr.ObjectClass` (3.2.29) (11.2.2.3)
    """

    # Redefine in this context as we need 'property' for the 11179 terminology.
    property_ = property
    template = "aristotle_mdr/concepts/dataElementConcept.html"
    objectClass = ConceptForeignKey(  # 11.2.3.3
        ObjectClass, blank=True, null=True,
        help_text=_('references an Object_Class that is part of the specification of the Data_Element_Concept'),
        verbose_name='Object Class',
        on_delete=models.SET_NULL
    )
    property = ConceptForeignKey(  # 11.2.3.1
        Property, blank=True, null=True,
        help_text=_('references a Property that is part of the specification of the Data_Element_Concept'),
        verbose_name='Property',
        on_delete=models.SET_NULL
    )
    conceptualDomain = ConceptForeignKey(  # 11.2.3.2
        ConceptualDomain, blank=True, null=True,
        help_text=_('references a Conceptual_Domain that is part of the specification of the Data_Element_Concept'),
        verbose_name='Conceptual Domain',
        on_delete=models.SET_NULL
    )

    related_objects = [
        'objectClass',
        'property'
    ]

    name_suggest_fields = ['objectClass', 'property']

    @property_
    def registry_cascade_items(self):
        out = []
        if self.objectClass:
            out.append(self.objectClass)
        if self.property:
            out.append(self.property)
        return out

    def get_download_items(self):

        return [
            ObjectClass.objects.filter(id=self.objectClass_id),
            Property.objects.filter(id=self.property_id),
        ]

    @property_
    def relational_attributes(self):
        return {
            "data_elements": {
                "all": _("Data Elements implementing this Data Element Concept"),
                "qs": self.dataelement_set.all()
            },
        }


# Yes this name looks bad - blame 11179:3:2013 for renaming "administered item"
# to "concept".
class DataElement(concept):
    """
    Unit of data that is considered in context to be indivisible (3.2.28)
    """

    template = "aristotle_mdr/concepts/dataElement.html"
    list_details_template = "aristotle_mdr/concepts/list_details/data_element.html"

    dataElementConcept = ConceptForeignKey(  # 11.5.3.2
        DataElementConcept,
        verbose_name="Data Element Concept",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text=_(
            "binds with a Value_Domain that describes a set of possible values that may be recorded in an instance of the Data_Element")
    )
    valueDomain = ConceptForeignKey(  # 11.5.3.1
        ValueDomain,
        verbose_name="Value Domain",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text=_("binds with a Data_Element_Concept that provides the meaning for the Data_Element")
    )

    related_objects = [
        'valueDomain',
        'dataElementConcept__objectClass',
        'dataElementConcept__property'
    ]

    name_suggest_fields = ['dataElementConcept', 'valueDomain']

    @property
    def registry_cascade_items(self):
        out = []
        if self.valueDomain:
            out.append(self.valueDomain)
        if self.dataElementConcept:
            out.append(self.dataElementConcept)
            out += self.dataElementConcept.registry_cascade_items
        return out

    def get_download_items(self):
        items = [
            DataElementConcept.objects.filter(id=self.dataElementConcept_id),
            ValueDomain.objects.filter(id=self.valueDomain_id)
        ]
        if self.dataElementConcept:
            items += self.dataElementConcept.get_download_items()
        return items

    # TODO: Can we refactor this to work on a set of objects instead of just one to speed up downloads.
    @property
    def relational_attributes(self):
        rels = {}
        if "aristotle_dse" in fetch_aristotle_settings().get('CONTENT_EXTENSIONS'):
            from aristotle_dse.models import DataSetSpecification, Distribution

            rels.update({
                "dss": {
                    "all": _("Inclusion in Data Set Specifications"),
                    "qs": DataSetSpecification.objects.filter(
                        dssdeinclusion__data_element=self
                    ).distinct()
                },
                "distributions": {
                    "all": _("Inclusion in Data Distributions"),
                    "qs": Distribution.objects.filter(
                        distributiondataelementpath__data_element=self
                    ).distinct()
                },
            })
        if "mallard_qr" in fetch_aristotle_settings().get('CONTENT_EXTENSIONS'):

            rels.update({
                "dss": {
                    "all": _("Use within a Question"),
                    "qs": self.questions.all(),
                },
            })
        return {**rels, **get_comet_indicator_relational_attributes(self)}  # Return both dictionaries combined.


class DataElementDerivation(concept):
    r"""
    Application of a derivation rule to one or more
    input :model:`aristotle_mdr.DataElement`\s to derive one or more
    output :model:`aristotle_mdr.DataElement`\s (3.2.33)
    """

    # edit_page_excludes = ['inputs', 'derives']
    serialize_weak_entities = [
        ('inputs', 'dedinputsthrough_set'),
        ('derives', 'dedderivesthrough_set'),
    ]

    @property
    def input_data_elements(self):
        return DataElement.objects.filter(dedinputsthrough__data_element_derivation=self)

    @property
    def derived_data_elements(self):
        return DataElement.objects.filter(dedderivesthrough__data_element_derivation=self)

    @property
    def inputs(self):
        return self.dedinputsthrough_set.all()

    @property
    def derives(self):
        return self.dedderivesthrough_set.all()

    derivation_rule = models.TextField(
        blank=True,
        help_text=_("text of a specification of a data element Derivation_Rule")
    )


class DedDerivesThrough(DedBaseThrough):
    pass


class DedInputsThrough(DedBaseThrough):
    pass


# Create a 1-1 user profile so we don't need to extend user
# Thanks to http://stackoverflow.com/a/965883/764357
class PossumProfile(models.Model):
    """
    Extension "one-to-one" class of the existing user model
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='profile',
        on_delete=models.PROTECT,
    )
    savedActiveWorkgroup = models.ForeignKey(
        Workgroup,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    profilePictureWidth = models.IntegerField(
        blank=True,
        null=True
    )
    profilePictureHeight = models.IntegerField(
        blank=True,
        null=True
    )
    profilePicture = ConvertedConstrainedImageField(
        blank=True,
        null=True,
        height_field='profilePictureHeight',
        width_field='profilePictureWidth',
        max_upload_size=((1024 ** 2) * 10),  # 10 MB
        content_types=['image/jpg', 'image/png', 'image/bmp', 'image/jpeg', 'image/x-ms-bmp'],
        js_checker=True
    )
    notificationPermissions = JSONField(
        default={
            "metadata changes": {
                "general changes": {
                    "items in my workgroups": True,
                    "items I have tagged / favourited": True,
                    "any items I can edit": True
                },
                "superseded": {
                    "items in my workgroups": True,
                    "items I have tagged / favourited": True,
                    "any items I can edit": True
                },
                "new items": {
                    "new items in my workgroups": True
                },
            },
            "registrar": {
                "item superseded": True,
                "item registered": True,
                "item changed status": True,
                "review request created": True,
                "review request updated": True
            },
            "issues": {
                "items in my workgroups": True,
                "items I have tagged / favourited": True,
                "any items I can edit": True
            },
            "discussions": {
                "new posts": True,
                "new comments": True
            },
            "notification methods": {
                "email": False,
                "within aristotle": True
            }
        }
    )

    def get_profile_picture_url(self):
        return reverse(
            "aristotle:profile_picture",
            args=[self.user.pk]
        )

    # Override save for inline creation of objects.
    # http://stackoverflow.com/questions/2813189/django-userprofile-with-unique-foreign-key-in-django-admin
    def save(self, *args, **kwargs):
        try:
            existing = PossumProfile.objects.get(user=self.user)
            self.id = existing.id  # Force update instead of insert.
        except PossumProfile.DoesNotExist:  # pragma: no cover
            pass

        models.Model.save(self, *args, **kwargs)

    @property
    def activeWorkgroup(self):
        return self.savedActiveWorkgroup or None

    def workgroups_for_user(self):
        return Workgroup.objects.filter(members__user=self.user)

    @property
    def workgroups(self):
        # All of the workgroups a user can see
        if self.user.is_superuser:
            return Workgroup.objects.all()
        else:
            return self.workgroups_for_user()

    @property
    def myWorkgroups(self):
        # All of the workgroups a user can participate in
        return self.workgroups_for_user().filter(archived=False)

    @property
    def myWorkgroupCount(self):
        return self.myWorkgroups.all().count()

    @property
    def mySandboxContent(self):
        """ Sandbox content is content:
            1. Submitted by the user
            2. That is not registered
            3. That is not under review or is for a review that has been revoked
            4. That has not been added to a workgroup"""
        from aristotle_mdr.contrib.reviews.const import REVIEW_STATES
        return _concept.objects.filter(
            Q(submitter=self.user,
              statuses__isnull=True
              ) & Q(Q(rr_review_requests__isnull=True) |
                    Q(rr_review_requests__status=REVIEW_STATES.revoked)
                    ) & Q(workgroup__isnull=True)
        )

    @property
    def editable_workgroups(self):
        # This list of workgroups a user can edit metadata in
        if self.user.is_superuser:
            return Workgroup.objects.all().order_by('name')
        else:
            # TODO: Managers *can* edit things in groups
            return Workgroup.objects.filter(
                members__role__in=["steward", "submitter", "manager"],
                members__user=self.user,
                archived=False
            )

    @property
    def is_registrar(self):
        return perms.user_is_registrar(self.user)

    @property
    def registrar_count(self):
        return self.user.registrar_in.count()

    @property
    def is_ra_manager(self):
        user = self.user
        if user.is_anonymous:
            return False
        if user.is_superuser:
            return True
        return RegistrationAuthority.objects.filter(managers__pk=user.pk).count() > 0

    @property
    def discussions(self):
        return DiscussionPost.objects.filter(
            workgroup__in=self.myWorkgroups.all()
        )

    @property
    def registrarAuthorities(self):
        # NOTE: This is a list of Authorities the user is a *registrar* in!.
        if self.user.is_superuser:
            return RegistrationAuthority.objects.all().order_by('name')
        else:
            return self.user.registrar_in.all().order_by('name')

    def is_workgroup_manager(self, wg=None):
        return perms.user_is_workgroup_manager(self.user, wg)

    def is_stewardship_organisation_admin(self, org=None):
        kwargs = {"user": self.user, "role": "admin"}
        if org:
            kwargs["group"] = org
        return StewardOrganisationMembership.objects.filter(**kwargs).exists()

    @property
    def stewardship_organisations(self):
        """The list of Stewardship Organisations the user is a member in, or all, if they are a superuser """
        if self.user.is_superuser:
            return StewardOrganisation.objects.all()
        else:
            # They are not a superuser
            return StewardOrganisation.objects.visible(self.user).filter(members__user=self.user)

    def is_favourite(self, item):
        from aristotle_mdr.contrib.favourites.models import Favourite
        fav = Favourite.objects.filter(
            tag__primary=True,
            tag__profile=self,
            item=item
        )
        return fav.exists()

    def toggleFavourite(self, item):
        from aristotle_mdr.contrib.favourites.models import Favourite, Tag

        if self.is_favourite(item):
            fav = Favourite.objects.filter(
                tag__primary=True,
                tag__profile=self,
                item=item
            )
            fav.delete()
            return False
        else:
            fav_tag, created = Tag.objects.get_or_create(
                profile=self,
                primary=True,
            )
            Favourite.objects.create(
                tag=fav_tag,
                item=item
            )
            return True

    @property
    def favourites(self):
        return _concept.objects.filter(
            favourites__tag__primary=True,
            favourites__tag__profile=self
        ).distinct()

    @property
    def favourite_item_pks(self):
        qs = _concept.objects.filter(
            favourites__tag__primary=True,
            favourites__tag__profile=self
        ).distinct().values_list('id', flat=True)
        return list(qs)

    @property
    def favs_and_tags_count(self):
        count = _concept.objects.filter(
            favourites__tag__profile=self
        ).distinct().count()
        return count

    def profile_picture_url(self):
        if self.profilePicture:
            return self.profilePicture.url
        else:
            return reverse("aristotle_mdr:dynamic_profile_picture", args=[self.user.id])


class SandboxShare(models.Model):
    uuid = models.UUIDField(
        help_text=_("Universally-unique Identifier. Uses UUID1 as "
                    "this improves uniqueness and ""tracking between registries"),
        unique=True,
        default=uuid.uuid1,
        editable=False,
        null=False
    )
    profile = models.OneToOneField(
        PossumProfile,
        related_name='share',
        on_delete=models.PROTECT,
    )
    created = models.DateTimeField(
        auto_now=True
    )
    emails = JSONField()

    def __str__(self):
        return str({'uuid': self.uuid,
                    'profile': self.profile,
                    'created': self.created,
                    'emails: ': self.emails
                    })


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        PossumProfile.objects.get_or_create(user=instance)


post_save.connect(create_user_profile, sender=settings.AUTH_USER_MODEL)


@receiver(post_save)
def concept_saved(sender, instance, **kwargs):
    if not issubclass(sender, _concept):
        return

    if not instance.non_cached_fields_changed:
        # If the only thing that has changed is a cached public/locked status
        # then don't notify.
        return
    if kwargs.get('raw'):
        # Don't run during loaddata
        return
    kwargs['changed_fields'] = instance.changed_fields
    # If the concept saved was not triggered by a superseding action:
    if not ('modified' in kwargs['changed_fields'] and len(kwargs['changed_fields']) == 1):
        fire("concept_changes.concept_saved", obj=instance, **kwargs)


@receiver(pre_save)
def check_concept_app_label(sender, instance, **kwargs):
    if not issubclass(sender, _concept):
        return
    if instance._meta.app_label not in fetch_metadata_apps():
        raise ImproperlyConfigured(
            (
                "Trying to save item <{instance_name}> when app_label <{app_label}> "
                "is not enabled. Metadata apps at this point were <{metadata_apps}>."
            ).format(
                app_label=instance._meta.app_label,
                instance_name=instance.name,
                metadata_apps=str(fetch_metadata_apps())
            )
        )


@receiver(pre_save)
def update_org_to_match_workgroup(sender, instance, **kwargs):
    """Enforces integrity between Stewardship Organisation and Workgroup"""
    if not issubclass(sender, _concept):
        return
    if instance.workgroup is not None:
        instance.stewardship_organisation = instance.workgroup.stewardship_organisation


@receiver(post_save, sender=DiscussionComment)
def new_comment_created(sender, instance, **kwargs):
    comment = instance
    post = comment.post
    if kwargs.get('raw'):
        # Don't run during loaddata
        return
    if not kwargs['created']:
        return  # We don't need to notify a topic poster of an edit.
    if comment.author == post.author:
        return  # We don't need to tell someone they replied to themselves
    fire("concept_changes.new_comment_created", obj=comment, **kwargs)


@receiver(post_save, sender=DiscussionPost)
def new_post_created(sender, instance, **kwargs):
    # Don't pass the instance to the JSONEncoder
    post = instance
    if kwargs.get('raw'):
        # Don't run during loaddata
        return
    if not kwargs['created']:
        return  # We don't need to notify a topic poster of an edit.
    fire("concept_changes.new_post_created", obj=post, **kwargs)


@receiver(post_save, sender=Status)
def states_changed(sender, instance, *args, **kwargs):
    fire("concept_changes.status_changed", obj=instance, **kwargs)


@receiver(post_save, sender=SupersedeRelationship)
def new_superseded_relation(sender, instance, *args, **kwargs):
    if kwargs.get('created'):
        fire("concept_changes.item_superseded", obj=instance, **kwargs)
