from rest_framework import serializers, pagination, viewsets
from aristotle_mdr.utils.utils import fetch_aristotle_settings


class DescriptionStubSerializerMixin(object):
    definition = serializers.SerializerMethodField()

    def get_definition(self, instance):
        from django.utils.html import strip_tags
        import re
        d = strip_tags(instance.definition)
        d = re.sub(r"\s+", " ", d, flags=re.UNICODE)
        d=d.split()
        if len(d) > 100:
            d = d[0:100] + ["..."]
        return " ".join(d)


class MultiSerializerViewSetMixin(viewsets.ReadOnlyModelViewSet):
    serializers: dict = {
        'default': None,
    }

    def get_serializer_class(self):
        return self.serializers.get(self.action, self.serializers['default'])


aristotle_apps = fetch_aristotle_settings().get('CONTENT_EXTENSIONS', [])
aristotle_apps += ["aristotle_mdr"]

api_excluded_fields = [
    "_concept_ptr",
    "_is_locked",
    "_is_public",
    "_type",
    "packages",
    "relatedDiscussions",
    "superseded_by",
    "supersedes",
    "version",
    "workgroup",
    'submitter',
]


def get_api_fields(cls):
    for field in cls._meta.get_fields():
        if field.name not in api_excluded_fields:
            f = field
            if not f.auto_created:  # because the new get_field() API will find "reverse" relations), and:
                if True:  # f.is_relation and f.related_model is None: #, because the new get_field() API will find GenericForeignKey relations;
                    yield field


class ConceptResultsPagination(pagination.PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class UUIDLookupModelMixin(object):
    lookup_field = 'uuid'
