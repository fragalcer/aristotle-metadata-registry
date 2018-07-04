from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import ugettext_lazy as _

from model_utils import Choices

from autoslug import AutoSlugField
from aristotle_mdr.utils import classproperty


class AbstractMembershipBase(ModelBase):
    group_class = None
    group_kwargs = {}

    def __new__(cls, name, bases, attrs):  # noqa
        clsobj = super().__new__(cls, name, bases, attrs)

        try:
            field = clsobj._meta.get_field("role")
            roles = clsobj.group_class.roles
            if clsobj.group_class.roles:
                field.choices = roles
        except FieldDoesNotExist:
            clsobj.add_to_class(
                "role",
                models.CharField(
                    # choices=clsobj.roles,
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
                )
            )

        return clsobj

class AbstractMembership(models.Model, metaclass=AbstractMembershipBase):
    class Meta:
        abstract = True
        unique_together = ("user", "group")

    user = models.ForeignKey(settings.AUTH_USER_MODEL)


class AbstractMultipleMembership(models.Model, metaclass=AbstractMembershipBase):
    class Meta:
        abstract = True
        unique_together = ("user", "group", "role")

    user = models.ForeignKey(settings.AUTH_USER_MODEL)


class AbstractGroupQuerySet(models.QuerySet):
    def group_list_for_user(self, user):
        return self.filter(members__user=user).distinct()

    def user_has_role(self, user, role):
        return self.filter(members__user=user, members__role=role).distinct()




class AbstractGroup(models.Model):
    objects = AbstractGroupQuerySet.as_manager()

    roles = Choices(
        ('owner', _('Owner')),
    )

    class Permissions:
        @classmethod
        def is_superuser(cls, user):
            return user.is_superuser

    role_permissions = {
        "edit_group_details": [roles.owner, Permissions.is_superuser],
        "edit_members": [roles.owner, Permissions.is_superuser],
        "invite_member": [roles.owner, Permissions.is_superuser],
    }

    class Meta:
        abstract = True
    
    slug = AutoSlugField(populate_from='name', editable=True, always_update=False)
    name = models.TextField(
        help_text=_("The primary name used for human identification purposes.")
    )
    
    @classproperty
    def allows_multiple_roles(self):
        return issubclass(self.members.rel.related_model, AbstractMultipleMembership)
    
    def __str__(self):
        return self.name

    @classmethod
    def user_has_permission(self, *args, **kwargs):
        # if permission not in self.role_permissions.keys()
        #     raise PermissionNotDefined
        print(self, *args, **kwargs)

        def allowed():
            for perm_or_role in self.role_permissions[permission]:
                if callable(perm_or_role):
                    perm = perm_or_role
                    yield perm(user)
                else:
                    role = perm_or_role
                    yield self.has_role(role, user)
        return any(allowed())

    @property
    def member_list(self):
        user_to_membership_relation = self.members.rel.related_model.user.field.related_query_name()
        return get_user_model().objects.filter(**{
            user_to_membership_relation+"__group": self
        })

    def has_role(self, role, user):
        """
        Returns true if the user has the specified role
        If role is a list, returns true if the user has any of the given roles
        """
        if type(role) is list:
            return self.members.filter(user=user, role__in=role).exists()
        return self.members.filter(user=user, role=role).exists()

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

