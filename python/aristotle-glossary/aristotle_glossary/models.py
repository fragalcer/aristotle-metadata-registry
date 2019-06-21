from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr import models as MDR
import reversion


class GlossaryItem(MDR.concept):
    template = "aristotle_glossary/concepts/glossaryItem.html"
    edit_page_excludes = ["index"]

    index = models.ManyToManyField(MDR._concept,blank=True,null=True,related_name="related_glossary_items")

    @property
    def relational_attributes(self):
        rels = {
            "related_metadata": {
                "all": _("Metadata that references this Glossary Item"),
                "qs": self.index.all()
            },
        }
        return rels

@reversion.register()
class GlossaryAdditionalDefinition(MDR.aristotleComponent):
    glossaryItem = models.ForeignKey(GlossaryItem,related_name="alternate_definitions")
    registrationAuthority = models.ForeignKey(MDR.RegistrationAuthority)
    definition = models.TextField()
    @property
    def parentItem(self):
        return self.glossaryItem
    class Meta:
        unique_together = ('glossaryItem', 'registrationAuthority',)


@receiver(post_save)
def add_concepts_to_glossary_index(sender, instance, created, **kwargs):
    if not issubclass(sender, MDR._concept):
        return
    if 'data-aristotle_glossary_id' in instance.definition:
        glossary_id = 1 # TODO: write code to find the id of the glossary item being inserted
        try:
            g = GlossaryItem.objects.get(pk=glossary_id)
        except GlossaryItem.DoesNotExist:
            pass # there is no glossary with that ID
            #TODO: Perhaps pass a friendly message - https://docs.djangoproject.com/en/1.7/ref/contrib/messages/


def reindex_metadata_item(item):
    if not issubclass(item.__class__, MDR._concept):
        return

    import lxml.html

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

    item.related_glossary_items.clear()
    related_list = []
    for field in fields + custom_fields:
        if 'data-aristotle-concept-id' in field:
            doc = lxml.html.fragment_fromstring(field, create_parent=True)
            links = doc.xpath('.//a')

            glossary_ids = [
                link.get('data-aristotle-concept-id')
                for link in links
                if link.get('data-aristotle-concept-id')
            ]
            item.related_glossary_items = GlossaryItem.objects.filter(pk__in=glossary_ids) 
            related_list = list(item.related_glossary_items.values_list("pk", flat=True))

    return item.related_glossary_items.all()
