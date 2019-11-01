from django.views.generic import TemplateView
from django.conf import settings


class APIRootView(TemplateView):
    template_name = "aristotle_mdr_api/base.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['graphql_enabled'] = settings.GRAPHQL_ENABLED
        return context
