from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from aristotle_mdr.utils import fetch_aristotle_settings

import uuid
import datetime

from model_utils.models import TimeStampedModel

from ckeditor_uploader.fields import RichTextUploadingField as RichTextField

from aristotle_mdr.fields import (
    ConceptForeignKey,
    ShortTextField,
)

from aristotle_mdr.managers import (
    MetadataItemManager,
    ManagedItemQuerySet,
    UtilsManager
)

VERY_RECENTLY_SECONDS = 15


class baseAristotleObject(TimeStampedModel):
    uuid = models.UUIDField(
        help_text=_(
            "Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries"
        ),
        unique=True,
        default=uuid.uuid1,
        editable=False,
        null=False,
    )
    name = ShortTextField(
        help_text=_("The primary name used for human identification purposes.")
    )
    definition = RichTextField(
        _('definition'),
        blank=True,
        default='',
        help_text=_("Representation of a concept by a descriptive statement "
                    "which serves to differentiate it from related concepts. (3.2.39)")
    )
    objects = MetadataItemManager()

    class Meta:
        # So the url_name works for items we can't determine
        verbose_name = "item"
        # Can't be abstract as we need unique app wide IDs.
        abstract = True

    @property
    def aristotle_id(self):
        """
        Id that can be displayed through infobox and graphql
        This is a property to allow for easy splitting of display id and internal id
        """
        return self.pk

    def was_modified_very_recently(self):
        return self.modified >= (
            timezone.now() - datetime.timedelta(seconds=VERY_RECENTLY_SECONDS)
        )

    def was_modified_recently(self):
        return self.modified >= timezone.now() - datetime.timedelta(days=1)

    was_modified_recently.admin_order_field = 'modified'  # type: ignore
    was_modified_recently.boolean = True  # type: ignore
    was_modified_recently.short_description = 'Modified recently?'  # type: ignore

    def description_stub(self):
        from django.utils.html import strip_tags
        d = strip_tags(self.definition)
        if len(d) > 150:
            d = d[0:150] + "..."
        return d

    def __str__(self):
        return "{name}".format(name=self.name)

    # Defined so we can access it during templates.
    @classmethod
    def get_verbose_name(cls):
        return cls._meta.verbose_name.title()

    @classmethod
    def get_verbose_name_plural(cls):
        return cls._meta.verbose_name_plural.title()

    def can_edit(self, user):
        # This should always be overridden
        raise NotImplementedError  # pragma: no cover

    def can_view(self, user):
        # This should always be overridden
        raise NotImplementedError  # pragma: no cover

    @classmethod
    def meta(cls):
        """
        The purpose of this function is to use the meta attribute in templates.
         example: "item.meta"
        :return: _meta attribute of class.
        """
        return cls._meta


class unmanagedObject(baseAristotleObject):
    class Meta:
        abstract = True

    def can_edit(self, user):
        return user.is_superuser

    def can_view(self, user):
        return True

    @property
    def item(self):
        return self


class ManagedItem(baseAristotleObject):
    """
    Managed items can be published, but not registered
    """
    class Meta:
        abstract = True

    objects = ManagedItemQuerySet.as_manager()

    publication_details = GenericRelation('aristotle_mdr_publishing.PublicationRecord')
    version_publication_details = GenericRelation('aristotle_mdr_publishing.VersionPublicationRecord')
    stewardship_organisation = models.ForeignKey(
        'aristotle_mdr.StewardOrganisation', to_field="uuid",
        null=False,
        on_delete=models.CASCADE,
    )
    # workgroup = models.ForeignKey('aristotle_mdr.Workgroup', null=True, blank=True)
    list_details_template = "aristotle_mdr/manageditems/helpers/list_details.html"

    def can_edit(self, user):
        return user.is_superuser

    def can_view(self, user):
        return self.__class__.objects.filter(pk=self.pk).visible(user).exists()

    @property
    def item(self):
        return self

    def get_absolute_url(self):
        return reverse(
            "aristotle_mdr:view_managed_item",
            # args=[self.slug],
            kwargs={
                "model_slug": self._meta.model.__name__.lower(),
                "iid": self.pk
            }
        )


class aristotleComponent(models.Model):

    uuid = models.UUIDField(
        help_text=_(
            "Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries"
        ),
        unique=True,
        default=uuid.uuid1,
        editable=False,
        null=False
    )

    objects = UtilsManager()
    ordering_field = 'order'

    # Parent is the parent item of the component
    parent_field_name: str = ''

    class Meta:
        abstract = True

    @property
    def parentItem(self):
        """Return the actual parent item or None if no parent item exists"""
        parent = getattr(self, 'parent_field_name')
        if parent == "":
            return None
        return getattr(self, parent)

    @property
    def parentItemId(self):
        """Return the id of the parent item"""
        parent = getattr(self, 'parent_field_name')
        parent_id = parent + '_id'
        return getattr(self, parent_id)

    @classmethod
    def get_parent_model(cls):
        """Get the model of the parent item"""
        if cls.parent_field_name == '':
            return None
        return cls._meta.get_field(cls.parent_field_name).related_model

    def can_edit(self, user):
        return self.parentItem.can_edit(user)

    def can_view(self, user):
        return self.parentItem.can_view(user)


class discussionAbstract(TimeStampedModel):
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True

    @property
    def edited(self):
        return self.created != self.modified


class AbstractValue(aristotleComponent):
    """
    Implementation note: Not the best name, but there will be times to
    subclass a "value" when its not just a permissible value.
    """

    value = ShortTextField(  # 11.3.2.7.2.1 - Renamed from permitted value for abstracts
        help_text=_("the actual value of the Value")
    )
    meaning = ShortTextField(  # 11.3.2.7.1
        help_text=_("A textual designation of a value, where a relation to a Value meaning doesn't exist"),
        blank=True
    )
    value_meaning = models.ForeignKey(  # 11.3.2.7.1
        'ValueMeaning',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text=_('A reference to the value meaning that this designation relates to')
    )
    # Below will generate exactly the same related name as django, but reversion-compare
    # needs an explicit related_name for some actions.
    valueDomain = ConceptForeignKey(
        'ValueDomain',
        related_name="%(class)s_set",
        help_text=_("Enumerated Value Domain that this value meaning relates to"),
        verbose_name='Value Domain',
        on_delete=models.CASCADE,
    )
    order = models.PositiveSmallIntegerField("Position")
    start_date = models.DateField(
        blank=True,
        null=True,
        help_text=_('Date at which the value became valid')
    )
    end_date = models.DateField(
        blank=True,
        null=True,
        help_text=_('Date at which the value ceased to be valid')
    )

    parent_field_name = 'valueDomain'

    class Meta:
        abstract = True
        ordering = ['order']

    def __str__(self):
        return "%s: %s - %s" % (
            self.valueDomain.name,
            self.value,
            self.meaning
        )


class DedBaseThrough(aristotleComponent):
    """
    Abstract Class for Data Element Derivation Many to Many through tables with ordering
    """

    data_element_derivation = models.ForeignKey('DataElementDerivation', on_delete=models.CASCADE)
    data_element = models.ForeignKey('DataElement', on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField("Position")
    objects = UtilsManager()

    parent_field_name = 'data_element_derivation'

    class Meta:
        abstract = True
        ordering = ['order']


def get_comet_indicator_relational_attributes(model_instance):
    """
    The purpose of this function is to retrieve the relational attributes
    from the Comet Indicator Registry, particularly from the
    IndicatorDataElementBase model.
    :param model_instance: The related model.
    :return: Dictionary containing relational attributes from the Comet extension.
    """
    rels = {}
    if "comet" in fetch_aristotle_settings().get('CONTENT_EXTENSIONS'):
        from comet.models import Indicator, IndicatorDataElementBase

        as_numerator_kwargs = {}
        as_denominator_kwargs = {}
        as_disaggregator_kwargs = {}

        for model_field in IndicatorDataElementBase._meta.get_fields():
            if model_field.is_relation and model_field.many_to_one:
                if model_field.related_model == model_instance._meta.model:
                    as_numerator_kwargs = {
                        'indicatornumeratordefinition__{}'.format(model_field.name): model_instance,
                    }
                    as_denominator_kwargs = {
                        'indicatordenominatordefinition__{}'.format(model_field.name): model_instance,
                    }
                    as_disaggregator_kwargs = {
                        'indicatordisaggregationdefinition__{}'.format(model_field.name): model_instance,
                    }

        rels.update({
            "as_numerator": {
                "all": _("As a numerator in an Indicator"),
                "qs": Indicator.objects.filter(**as_numerator_kwargs).distinct()
            },
            "as_denominator": {
                "all": _("As a denominator in an Indicator"),
                "qs": Indicator.objects.filter(**as_denominator_kwargs).distinct()
            },
            "as_disaggregator": {
                "all": _("As a disaggregation in an Indicator"),
                "qs": Indicator.objects.filter(**as_disaggregator_kwargs).distinct()
            },
        })
    return rels
