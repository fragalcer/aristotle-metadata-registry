from typing import Dict
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import ugettext_lazy as _

from model_utils import Choices
import uuid

from autoslug import AutoSlugField
from aristotle_mdr.utils import classproperty

from . import managers

import logging
logger = logging.getLogger(__name__)


class AbstractMembershipBase(ModelBase):
    group_class = None
    group_kwargs: Dict[str, str] = {}

    def __new__(mcs, name, bases, attrs):  # noqa
        clsobj = super().__new__(mcs, name, bases, attrs)

        try:
            field = clsobj._meta.get_field("role")
            roles = clsobj.group_class.roles
            if clsobj.group_class.roles:
                field.choices = roles
        except FieldDoesNotExist:
            clsobj.add_to_class(
                "role",
                models.CharField(
                    max_length=128,
                    help_text=_('Role within this group')
                )
            )

        if clsobj.group_class is not None:
            clsobj.add_to_class(
                "group",
                models.ForeignKey(
                    clsobj.group_class,
                    related_name="members",
                    **clsobj.group_kwargs,
                    on_delete=models.CASCADE
                )
            )

        return clsobj


class AbstractMembershipModel(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def user_has_role_for_any_group(cls, user, role):
        return cls.objects.filter(user=user, role=role).exists()


class AbstractMembership(AbstractMembershipModel, metaclass=AbstractMembershipBase):
    class Meta:
        abstract = True
        unique_together = ("user", "group")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class AbstractMultipleMembership(AbstractMembershipModel, metaclass=AbstractMembershipBase):
    class Meta:
        abstract = True
        unique_together = ("user", "group", "role")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class AbstractGroupBase(ModelBase):
    def __new__(mcs, name, bases, attrs):  # noqa
        clsobj = super().__new__(mcs, name, bases, attrs)

        try:
            field = clsobj._meta.get_field("state")
            field.choices = clsobj.states
        except FieldDoesNotExist:
            clsobj.add_to_class(
                "state",
                models.CharField(
                    choices=clsobj.states,
                    default=clsobj.active_states[0],
                    max_length=128,
                    help_text=_('Status of this group')
                )
            )

        return clsobj


class BaseManager(models.Manager):
    pass


class AbstractGroup(models.Model, metaclass=AbstractGroupBase):
    objects = managers.AbstractGroupQuerySet.as_manager()
    can_invite_new_users_via_email = True

    class Meta:
        abstract = True

    roles = Choices(
        ('owner', _('Owner')),
        ('member', _('Member')),
    )
    states = Choices(
        ('active', _('Active')),
        ('disabled', _('Disabled')),
    )

    owner_roles = [roles.owner]
    new_member_role = roles.member

    active_states = [
        states.active,
    ]
    visible_states = [
        states.active, states.disabled
    ]

    class Permissions:
        @classmethod
        def is_superuser(cls, user, group=None):
            return user.is_superuser

        @classmethod
        def is_member(cls, user, group):
            if user.is_anonymous:
                return False
            if not group.is_active():
                return False
            return group.has_member(user)

    role_permissions = {
        "edit_group_details": [roles.owner, Permissions.is_superuser],
        "edit_members": [roles.owner, Permissions.is_superuser],
        "invite_member": [roles.owner, Permissions.is_superuser],
        "view_group": [Permissions.is_member],
    }

    slug = AutoSlugField(populate_from='name', editable=True, always_update=False, unique=True)
    uuid = models.UUIDField(
        unique=True, default=uuid.uuid1, editable=False, null=False
    )
    name = models.TextField(
        help_text=_("The primary name used for human identification purposes.")
    )

    def is_active(self):
        return self.state in self.active_states

    def is_owner(self, user):
        return self.has_role(user=user, role=self.owner_roles)

    @classproperty
    def allows_multiple_roles(self):
        return issubclass(self.members.rel.related_model, AbstractMultipleMembership)

    def __str__(self):
        return self.name

    def user_has_permission(self, user, permission):
        if user.is_superuser:
            return True

        def allowed():
            for perm_or_role in self.role_permissions[permission]:
                if callable(perm_or_role):
                    perm = perm_or_role
                    yield perm(user, group=self)
                else:
                    if user.is_anonymous:
                        yield False
                    elif not self.is_active():
                        yield False
                    else:
                        role = perm_or_role
                        yield self.has_role(role, user)

        return any(allowed())

    @property
    def member_list(self):
        # user_to_membership_relation = self.members.rel.related_model.user.field.related_query_name()
        user_to_membership_relation = self.members.model.user.field.related_query_name()
        return get_user_model().objects.filter(**{
            user_to_membership_relation + "__group": self
        })

    def has_role(self, role, user):
        """
        Returns true if the user has the specified role
        If role is a list, returns true if the user has any of the given roles
        """
        if type(role) is list:
            return self.members.filter(user=user, role__in=role).exists()
        return self.members.all().filter(user=user, role=role).exists()

    def grant_role(self, role, user):
        """
        Returns false if the user already had the given role
        """

        if self.allows_multiple_roles:
            role, created = self.members.model.objects.get_or_create(
                group=self, user=user, role=role
            )
        else:
            role, created = self.members.model.objects.update_or_create(
                group=self, user=user,
                defaults={"role": role}
            )

        return created

    def revoke_role(self, role, user):
        """
        Remove given role for the user
        If role is a list, removes all of the given roles for the user
        Returns number of roles deleted
        """
        if type(role) is list:
            return self.members.filter(user=user, role__in=role).delete()
        return self.members.filter(user=user, role=role).delete()

    def revoke_membership(self, user):
        """
        Removes all roles.
        Returns number of roles deleted
        """
        deleted = self.members.filter(user=user).delete()
        return deleted

    def roles_for_user(self, user):
        """
        Returns a list of roles the user has in this group
        """
        return list(self.members.filter(user=user).values_list('role', flat=True))

    def users_for_role(self, role):
        """
        Returns a list of users with the given roles in this group
        """
        if type(role) is list:
            roles = role
        else:
            roles = [role]
        user_to_membership_relation = self.members.model.user.field.related_query_name()
        return get_user_model().objects.filter(**{
            user_to_membership_relation + "__group": self,
            user_to_membership_relation + "__role__in": roles
        })

    def has_member(self, user):
        """
        Returns true if the user is a member and has any role
        """
        return self.members.all().filter(user=user).exists()
