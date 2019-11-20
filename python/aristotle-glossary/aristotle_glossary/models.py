from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.async_signals.utils import fire


class GlossaryItem(MDR.concept):
    template = "aristotle_glossary/concepts/glossaryItem.html"
    edit_page_excludes = ["index"]

    index = models.ManyToManyField(MDR._concept, blank=True, related_name="related_glossary_items")

    @property
    def relational_attributes(self):
        rels = {
            "related_metadata": {
                "all": _("Metadata that references this Glossary Item"),
                "qs": self.index.all()
            },
        }
        return rels


@receiver(post_save)
def add_concepts_to_glossary_index(sender, instance, created, **kwargs):
    if not issubclass(sender, MDR._concept):
        return
    fire("reindex_metadata_item_async", obj=instance, **kwargs, namespace="aristotle_glossary.async_signals")


def item_is_owner_of_component(field_model, item_model):
    parent_model = field_model.get_parent_model()
    if not parent_model:
        return True
    else:
        if parent_model is item_model:
            return True
    return False


def is_rich_text_field(field):
    if issubclass(field.__class__, MDR.RichTextField):
        return True
    return False


def reindex_metadata_item(item):
    """Set the list of related glossary items """
    import lxml.html
    from lxml import etree

    if not issubclass(item.__class__, MDR._concept):
        return

    field_values = []

    for field in item._meta.get_fields():
        if is_rich_text_field(field):
            field_values.append(field.value_from_object(item))

        elif field.is_relation:
            component_model = field.related_model
            item_owns_component = (issubclass(component_model, MDR.aristotleComponent) and
                                   item_is_owner_of_component(component_model, type(item)))
            if item_owns_component:
                rich_text_fields = []
                for component_field in component_model._meta.get_fields():
                    # Get all the rich text fields for a particular component
                    if is_rich_text_field(component_field):
                        rich_text_fields.append(component_field)

                aristotle_components = getattr(item, field.get_accessor_name()).all()

                for component in aristotle_components:
                    # Get the value from each rich text field
                    for rich_text_field in rich_text_fields:
                        field_values.append(rich_text_field.value_from_object(component))
    custom_fields = [
        cv.content
        for cv in item.customvalue_set.all()
        if cv.is_html
    ]

    links = etree.XPath("//a[@data-aristotle-concept-id]")
    glossary_ids = []
    for field in field_values + custom_fields:
        if 'data-aristotle-concept-id' in field:
            doc = lxml.html.fragment_fromstring(field, create_parent=True)

            glossary_ids.extend([
                link.get('data-aristotle-concept-id')
                for link in links(doc)
            ])

    item.related_glossary_items.set(
        GlossaryItem.objects.filter(pk__in=glossary_ids), clear=True
    )

    return item.related_glossary_items.all()
