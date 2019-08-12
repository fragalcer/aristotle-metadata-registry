from django_filters.filterset import FilterSet
import django_filters


class AristotleFilterSet(FilterSet):
    aristotle_id = django_filters.CharFilter(field_name='id')


class IdentifierFilterSet(FilterSet):
    namespace = django_filters.CharFilter(field_name='namespace__shorthand_prefix', lookup_expr='iexact', distinct=True)

    class Meta:
        fields = ['namespace']


class StatusFilterSet(FilterSet):
    is_current = django_filters.BooleanFilter(method='filter_is_current')
    ra = django_filters.CharFilter(field_name='registrationAuthority__uuid', lookup_expr='iexact', distinct=True)

    class Meta:
        fields = ['is_current', 'ra']

    def filter_is_current(self, qs, name, value):
        if name == "is_current" and value:
            return qs.current()
        else:
            return qs


class ConceptFilterSet(FilterSet):
    aristotle_id = django_filters.CharFilter(field_name='id')
    identifier = django_filters.CharFilter(field_name='identifiers__identifier', lookup_expr='iexact', distinct=True)
    identifier_namespace = django_filters.CharFilter(field_name='identifiers__namespace__shorthand_prefix', lookup_expr='iexact', distinct=True)
    identifier_version = django_filters.CharFilter(field_name='identifiers__version', lookup_expr='iexact', distinct=True)
