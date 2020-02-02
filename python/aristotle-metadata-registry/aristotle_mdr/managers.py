from typing import Iterable
from django.db import models
from django.db.models import Q, Subquery
from django.utils import timezone
from django.utils.module_loading import import_string
from django.core.exceptions import ObjectDoesNotExist
from model_utils.managers import InheritanceManager, InheritanceQuerySet

from aristotle_mdr.contrib.reviews.const import REVIEW_STATES
from aristotle_mdr.constants import visibility_permission_choices
from aristotle_mdr.contrib.groups.managers import AbstractGroupQuerySet


class PublishedMixin(object):
    def visible(self, user):
        """
        Returns a queryset that returns all managed items that the given user has
        permission to view.

        It is **chainable** with other querysets.
        """
        if user.is_superuser:
            return self.all()

        q = self.is_published_public
        if user.is_anonymous:
            return self.filter(q)

        q |= self.is_published_auth

        return self.filter(q)

    def public(self):
        """
        Returns a queryset that returns all published items

        It is **chainable** with other querysets.
        """
        q = self.is_published_public
        return self.filter(q)

    @property
    def is_published_public(self):
        return Q(
            publication_details__permission=visibility_permission_choices.public,
            publication_details__publication_date__lte=timezone.now(),
        )

    @property
    def is_published_auth(self):
        return Q(
            publication_details__permission=visibility_permission_choices.auth,
            publication_details__publication_date__lte=timezone.now()
        )


class UtilsManager(models.Manager):
    """Manager with extra util functions"""

    def bulk_delete(self, objects: Iterable[models.Model]):
        if isinstance(objects, models.QuerySet):
            objects.delete()
        else:
            ids = [o.id for o in objects]
            qs = self.get_queryset().filter(id__in=ids)
            qs.delete()

    def get_object_or_none(self, **kwargs):
        try:
            return self.get(**kwargs)
        except ObjectDoesNotExist:
            return None


class MetadataItemQuerySet(InheritanceQuerySet):
    pass


class MetadataItemManager(InheritanceManager, UtilsManager):
    def get_queryset(self):
        from django.conf import settings

        qs = MetadataItemQuerySet(self.model, using=self._db)
        if hasattr(settings, 'FORCE_METADATAMANAGER_FILTER'):
            qs = qs.filter(*import_string(settings.FORCE_METADATAMANAGER_FILTER)())
        return qs


class StewardOrganisationQuerySet(AbstractGroupQuerySet):
    def visible(self, user):
        from aristotle_mdr.models import StewardOrganisation

        if user is None or user.is_anonymous:
            return self.filter(
                state__in=[
                    StewardOrganisation.states.active,
                    StewardOrganisation.states.archived,
                ],
            )

        if user.is_superuser:
            return self.all()

        # If you are a member, you can see the Workgroup
        q = Q(
            members__user=user,
            state__in=[
                StewardOrganisation.states.active,
                StewardOrganisation.states.private,
            ],
        )
        # If you are the admin of a SO, you can see all the WGs.
        q |= Q(
            state__in=[
                StewardOrganisation.states.active,
                StewardOrganisation.states.archived,
                StewardOrganisation.states.private,
            ],
            members__user=user,
            members__role=StewardOrganisation.roles.admin
        )

        inner_so_qs = StewardOrganisation.objects.filter(q)
        return self.filter(uuid__in=Subquery(inner_so_qs.values('uuid')))


class WorkgroupQuerySet(AbstractGroupQuerySet):
    def visible(self, user):
        if user.is_anonymous:
            return self.none()

        if user.is_superuser:
            return self.all()

        from aristotle_mdr.models import StewardOrganisation
        WG_STATES = StewardOrganisation.states

        if user.is_superuser:
            return self.all()

        # If you are a member, you can see the Workgroup
        q = Q(
            members__user=user,
        )
        # If you are the admin of a SO, you can see all the WGs.
        q |= Q(
            stewardship_organisation__state__in=[
                StewardOrganisation.states.active,
                StewardOrganisation.states.archived,
                StewardOrganisation.states.private,
            ],
            stewardship_organisation__members__user=user,
            stewardship_organisation__members__role=StewardOrganisation.roles.admin
        )
        return self.filter(q)


class RegistrationAuthorityQuerySet(models.QuerySet):
    def visible(self, user):
        from aristotle_mdr.models import RA_ACTIVE_CHOICES, StewardOrganisation

        if user.is_superuser:
            return self.all()

        q = Q(
            # If the RA is NOT hidden **AND**
            ~Q(active=RA_ACTIVE_CHOICES.hidden) &
            Q(
                # AND the SO is visible
                Q(stewardship_organisation__state__in=[
                    StewardOrganisation.states.active,
                    StewardOrganisation.states.archived,
                ]) |
                # OR you are a member of the SO.
                Q(
                    stewardship_organisation__state=StewardOrganisation.states.private,
                    stewardship_organisation__members__user=user,
                )
            )
        )
        return self.filter(q)


class ConceptQuerySet(PublishedMixin, MetadataItemQuerySet):
    def visible(self, user):
        """
        Returns a queryset that returns all items that the given user has
        permission to view.

        It is **chainable** with other querysets. For example, both of these
        will work and return the same list::

            ObjectClass.objects.filter(name__contains="Person").visible()
            ObjectClass.objects.visible().filter(name__contains="Person")
        """
        need_distinct = False  # Whether we need to add a distinct
        from aristotle_mdr.models import StewardOrganisation
        from aristotle_mdr.models import Workgroup

        if user is None or user.is_anonymous or not user.is_active:
            return self.public()
        if user.is_superuser:
            return self.all()
        if user.perm_view_all_metadata:
            return self.all()
        is_cached_public = Q(_is_public=True)

        # User can see everything they've made thats not assigned to an SO.
        user_is_submitter = Q(submitter=user)

        # User can see everything in their workgroups.
        workgroups = Workgroup.objects.filter(members__user=user, archived=False)
        user_in_workgroup = Q(workgroup__in=Subquery(workgroups.values('pk')))

        inner_qs = self
        inner_qs = inner_qs.filter(
            # Registars can see items they have been asked to review
            Q(
                Q(rr_review_requests__registration_authority__registrars__profile__user=user) &
                ~Q(rr_review_requests__status=REVIEW_STATES.revoked)
            ) |
            # Registars can see items that have been registered in their registration authority
            Q(
                Q(statuses__registrationAuthority__registrars__profile__user=user)
            )

        )
        item_is_for_registrar = Q(id__in=Subquery(inner_qs.values('pk')))

        item_is_published = self.is_published_public | self.is_published_auth

        inner_so_qs = StewardOrganisation.objects.filter(
            # The metadata belongs to an SO that is visible
            Q(state__in=[
                StewardOrganisation.states.active,
                StewardOrganisation.states.archived,
            ]) |
            # Or the SO or the metadata is private and you are a member of the SO.
            Q(
                state=StewardOrganisation.states.private,
                members__user=user,
            )
        )

        # If the metadata belongs to an SO, check the user can see it
        item_not_assigned_to_org = Q(stewardship_organisation__isnull=True)
        item_in_allowed_org = Q(
            stewardship_organisation__isnull=False,
            stewardship_organisation__in=Subquery(inner_so_qs.values('uuid'))
        )

        q = Q(
            Q(
                user_is_submitter |
                is_cached_public |
                user_in_workgroup |
                item_is_published |
                item_is_for_registrar
            ) &
            Q(item_in_allowed_org | item_not_assigned_to_org)
        )

        return self.filter(q)

    def editable(self, user):
        """
        Returns a queryset that returns all items that the given user has
        permission to edit.

        It is **chainable** with other querysets. For example, both of these
        will work and return the same list::

            ObjectClass.objects.filter(name__contains="Person").editable()
            ObjectClass.objects.editable().filter(name__contains="Person")
        """
        from aristotle_mdr.models import StewardOrganisation
        if user.is_superuser:
            return self.all()
        if user.is_anonymous:
            return self.none()
        q = Q()

        # User can edit everything they've made thats not locked
        q |= Q(submitter=user, _is_locked=False)

        editable_items = self.all().filter(
            Q(
                workgroup__members__role__in=['submitter', 'steward', 'manager'],
                workgroup__members__user=user,
                workgroup__archived=False,
                _is_locked=False
            ) | Q(
                workgroup__members__role__in=['steward', 'manager'],
                workgroup__members__user=user,
                workgroup__archived=False,
                _is_locked=True
            )
        )
        q |= Q(id__in=Subquery(editable_items.values('pk')))

        return self.filter(
            q &
            ~Q(stewardship_organisation__state=StewardOrganisation.states.hidden)
        )

    def public(self):
        """
        Returns a list of public items from the queryset.

        This is a chainable query set, that filters on items which have the
        internal `_is_public` flag set to true.

        Both of these examples will work and return the same list::

            ObjectClass.objects.filter(name__contains="Person").public()
            ObjectClass.objects.public().filter(name__contains="Person")
        """
        from aristotle_mdr.models import StewardOrganisation
        return self.filter(
            Q(self.is_published_public | Q(_is_public=True)) &
            ~Q(stewardship_organisation__state__in=[
                StewardOrganisation.states.hidden,
                StewardOrganisation.states.private
            ])
        )

    def with_related(self):
        related = self.model.related_objects
        if related:
            return self.select_related(*related)
        return self

    def __contains__(self, item):
        from aristotle_mdr.models import _concept

        if not issubclass(type(item), _concept):
            return False
        else:
            return self.all().filter(pk=item.concept.pk).exists()


class ConceptManager(MetadataItemManager):
    """
    The ``ConceptManager`` is the default object manager for ``concept`` and
    ``_concept`` items, and extends from the django-model-utils
    ``InheritanceManager``.

    It provides access to the ``ConceptQuerySet`` to allow for easy
    permissions-based filtering of ISO 11179 Concept-based items.
    """
    def get_queryset(self):
        from django.conf import settings

        qs = ConceptQuerySet(self.model, using=self._db)
        if hasattr(settings, 'FORCE_CONCEPTMANAGER_FILTER'):
            qs = qs.filter(*import_string(settings.FORCE_CONCEPTMANAGER_FILTER)())
        return qs
        # return ConceptQuerySet(self.model)

    def __getattr__(self, attr, *args):
        if attr in ['editable', 'visible', 'public']:
            return getattr(self.get_queryset(), attr, *args)
        else:
            return getattr(self.__class__, attr, *args)


class ReviewRequestQuerySet(models.QuerySet):
    def visible(self, user):
        """
        Returns a queryset that returns all reviews that the given user has
        permission to view.

        It is **chainable** with other querysets.
        """
        needs_distinct = False

        if user.is_superuser:
            return self.all()
        if user.is_anonymous:
            return self.none()
        q = Q(requester=user)  # Users can always see reviews they requested
        if user.profile.is_registrar:
            needs_distinct = True
            # Registars can see reviews for the registration authority
            q |= Q(
                Q(registration_authority__registrars__profile__user=user) &
                ~Q(status=REVIEW_STATES.revoked)
            )

        if needs_distinct:
            return self.filter(q).distinct()

        return self.filter(q)


class StatusQuerySet(models.QuerySet):
    def visible(self, user):
        """
        Returns a queryset that returns all statuses that the given user has
        permission to view.

        It is **chainable** with other querysets.
        """
        return self.all()

    def valid(self):
        return self.valid_at_date(timezone.now().date())

    def valid_at_date(self, when=None):
        if when is None:
            when = timezone.now().date()

        registered_before_now = Q(registrationDate__lte=when)
        registration_still_valid = (
            Q(until_date__gte=when) |
            Q(until_date__isnull=True)
        )

        return self.filter(
            registered_before_now & registration_still_valid
        )

    def current(self, when=None):
        """
        Returns a queryset that returns the most up to date statuses

        It is **chainable** with other querysets.
        """
        if when is None:
            when = timezone.now()
        if hasattr(when, 'date'):
            when = when.date()

        states = self.valid_at_date(when)
        states = states.order_by("registrationAuthority", "concept_id", "-registrationDate", "-created", )

        from django.db import connection
        if connection.vendor == 'postgresql':
            states = states.distinct('registrationAuthority', 'concept_id')
        else:
            current_ids = []
            seen_ras = []
            for s in states:
                ra = s.registrationAuthority
                if ra not in seen_ras:
                    current_ids.append(s.pk)
                    seen_ras.append(ra)
            # We hit again so we can return this as a queryset
            states = states.filter(pk__in=current_ids)

        return states.select_related('registrationAuthority')


class SupersedesQueryset(models.QuerySet):
    def visible(self, user):
        from aristotle_mdr.models import _concept
        visible_concepts = _concept.objects.visible(user)

        if user.is_superuser:
            return self.all()

        return self.filter(
            newer_item__in=visible_concepts,
            older_item__in=visible_concepts,
        )

    def approved(self):
        return self.filter(proposed=False)

    def proposed(self):
        return self.filter(proposed=True)


class ApprovedSupersedesQueryset(SupersedesQueryset):
    def queryset(self):
        return super().filter(proposed=False)


class ProposedSupersedesQueryset(SupersedesQueryset):
    def queryset(self):
        return super().filter(proposed=True)


class PublishedItemQuerySet(PublishedMixin, models.QuerySet):
    pass


class ManagedItemQuerySet(PublishedItemQuerySet):

    def editable(self, user):
        """
        Returns a queryset that returns all managed items that the given user has
        permission to edit.

        It is **chainable** with other querysets.
        """
        if user.is_superuser:
            return self.all()
        if user.is_anonymous:
            return self.none()

        from aristotle_mdr.models import StewardOrganisation

        q = Q(
            stewardship_organisation__members__user=user,
            stewardship_organisation__members__role__in=[
                StewardOrganisation.roles.admin, StewardOrganisation.roles.steward
            ]
        )

        return self.filter(q)
