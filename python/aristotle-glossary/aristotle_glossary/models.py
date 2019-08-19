from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.async_signals.utils import fire
import reversion


class GlossaryItem(MDR.concept):
    template = "aristotle_glossary/concepts/glossaryItem.html"
    edit_page_excludes = ["index"]

    index = models.ManyToManyField(MDR._concept, blank=True, null=True, related_name="related_glossary_items")

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


def reindex_metadata_item(item):
    import lxml.html
    from lxml import etree

    if not issubclass(item.__class__, MDR._concept):
        return

    fields = [
        field.value_from_object(item)
        for field in item._meta.fields
        if issubclass(field.__class__, MDR.RichTextField)
    ]
    custom_fields = [
        cv.content
        for cv in item.customvalue_set.all()
        if cv.is_html
    ]

    links = etree.XPath("//a[@data-aristotle-concept-id]")
    glossary_ids = []
    for field in fields + custom_fields:
        if 'data-aristotle-concept-id' in field:
            doc = lxml.html.fragment_fromstring(field, create_parent=True)
            # links = find(doc)

            glossary_ids.extend([
                link.get('data-aristotle-concept-id')
                for link in links(doc)
            ])

    item.related_glossary_items.set(
        GlossaryItem.objects.filter(pk__in=glossary_ids), clear=True
    )

    return item.related_glossary_items.all()
