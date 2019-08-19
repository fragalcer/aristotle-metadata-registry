from datetime import timedelta
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from haystack.views import FacetedSearchView

from aristotle_mdr.search_indexes import SEARCH_CATEGORIES


class PermissionSearchView(FacetedSearchView):

    results_per_page_values = getattr(settings, 'RESULTS_PER_PAGE', [])

    def build_page(self):

        try:
            results_per_page = self.form.cleaned_data['rpp']
        except (AttributeError, KeyError):
            results_per_page = ''

        if results_per_page in self.results_per_page_values:
            self.results_per_page = results_per_page
        else:
            if len(self.results_per_page_values) > 0:
                self.results_per_page = self.results_per_page_values[0]

        return super().build_page()

    def build_form(self):

        form = super().build_form()
        form.request = self.request
        form.request.GET = self.clean_facets(self.request)
        return form

    def clean_facets(self, request):
        get = request.GET.copy()
        for k, val in get.items():
            if k.startswith('f__'):
                get.pop(k)
                k = k[4:]
                get.update({'f': '%s::%s' % (k, val)})
        return get

    @cached_property
    def search_category_map(self):
        from haystack import connections
        from collections import defaultdict
        from haystack.constants import DEFAULT_ALIAS
        unified_index = connections[DEFAULT_ALIAS].get_unified_index()
        mapping = defaultdict(list)
        for model, index in unified_index.get_indexes().items():
            mapping[index.search_category].append(
                "%s.%s" % (model._meta.app_label, model._meta.model_name)
            )

        return dict(mapping)

    def extra_context(self):
        # needed to compare to indexed primary key value
        recently_viewed = {}
        favourites_list = []
        last_month = now() - timedelta(days=31)
        if not self.request.user.is_anonymous:
            from django.db.models import Count, Max
            favourites_list = self.request.user.profile.favourite_item_pks
            recently_viewed = dict(
                (
                    row["concept"],
                    {
                        "count": row["count_viewed"],
                        "last_viewed": row["last_viewed"]
                    }
                )
                for row in self.request.user.recently_viewed_metadata.all().filter(
                    view_date__gt=last_month
                ).values(
                    "concept"
                ).annotate(
                    count_viewed=Count('concept'),
                    last_viewed=Max("view_date")
                )
            )

        try:
            searched_category = SEARCH_CATEGORIES[self.request.GET.get("category")]
        except KeyError:
            searched_category = _("Metadata")

        return {
            'rpp_values': self.results_per_page_values,
            'favourites': favourites_list,
            'recently_viewed': recently_viewed,
            'searched_category': searched_category,
            'category_map': self.search_category_map
        }
