from typing import List, Dict
import datetime
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.apps import apps
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _

from model_utils import Choices

from haystack import connections
from haystack.constants import DEFAULT_ALIAS, DJANGO_ID
from haystack.forms import FacetedSearchForm, model_choices
from haystack.query import EmptySearchQuerySet, SearchQuerySet, SQ
from haystack.inputs import AutoQuery

import aristotle_mdr.models as MDR
from aristotle_mdr.widgets.bootstrap import (
    BootstrapDropdownSelectMultiple,
    BootstrapDropdownIntelligentDate,
    BootstrapDropdownSelect,
    BootstrapDateTimePicker,
    BootstrapDropdownSearchCategoriesSelect
)

from aristotle_mdr.utils import fetch_metadata_apps
from aristotle_mdr.search_indexes import SEARCH_CATEGORIES

import logging
logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)

QUICK_DATES = Choices(
    ('', 'anytime', _('Any time')),
    ('h', 'hour', _('Last hour')),
    ('t', 'today', _('Today')),
    ('w', 'week', _('This week')),
    ('m', 'month', _('This month')),
    ('y', 'year', _('This year')),
    ('X', 'custom', _('Custom period')),
)


# For dates and times, ascending means that earlier dates will precede later ones.
SORT_OPTIONS = Choices(
    ('n', 'natural', _('Relevance')),
    ('md', 'modified_descending', _('Most Recently Modified')),
    ('ma', 'modified_ascending', _('Least Recently Modified')),
    ('ca', 'created_ascending', _('First Created')),
    ('cd', 'created_descending', _('Last Created')),
    ('aa', 'alphabetical', _('Alphabetical')),
    ('s', 'state', _('Registration state')),
)

SHORT_STATE_MAP = {
    "i": "incomplete",
    "inc": "incomplete",
    "c": "candidate",
    "can": "candidate",
    "rec": "recorded",
    "q": "qualified",
    "qual": "qualified",
    "st": "standard",
    "p": "preferred",
    "pre": "preferred",
    "pref": "preferred",
    "sup": "superseded",
    "ret": "retired",
}


def allowable_search_models():
    return fetch_metadata_apps() + [
        'aristotle_mdr_help',
        'aristotle_mdr_stewards',
    ] + getattr(settings, 'ARISTOTLE_SEARCH_EXTRA_MODULES', [])


# This function is not critical and are mathematically sound, so testing is not required.
def time_delta(delta):  # pragma: no cover
    """
    Datetimes are expensive to search on, so this function gives approximations of the time options.
    Absolute precision can be used using the custom ranges, but may be slower.
    These approximations mean that similar ranges can be used in the haystack index when searching.
    """
    if delta == QUICK_DATES.hour:
        """
        The last hour, actually translates to the begin of the last hour, so
        this returns objects between 60 and 119 mintues ago.
        """
        n = datetime.datetime.now()
        n = datetime.datetime.combine(n.date(), datetime.time(hour=n.time().hour))
        return n - datetime.timedelta(hours=1)
    elif delta == QUICK_DATES.today:
        """
        Today returns everything today.
        """
        return datetime.date.today()  # - datetime.timedelta(days=1)
    elif delta == QUICK_DATES.week:
        """
        This week is pretty straight forward. SSReturns 7 days ago from the *beginning* of today.
        """
        return datetime.date.today() - datetime.timedelta(days=7)
    elif delta == QUICK_DATES.month:
        """
        This goes back to this day last month, and then finds the prior day thats
        divisible by 7 (not less than 1).
          1-6 -> 1
         7-13 -> 7
        14-20 -> 14
        21-27 -> 21
        28-31 -> 28
        """
        t = datetime.date.today()
        last_month = datetime.date(day=1, month=t.month, year=t.year) - datetime.timedelta(days=1)
        days = max(((t.day) // 7) * 7, 1)
        last_month = datetime.date(day=days, month=last_month.month, year=last_month.year)
        return datetime.date(day=1, month=last_month.month, year=last_month.year)
    elif delta == QUICK_DATES.year:
        """
        This goes back to the beginning of this month last year.
        So it searchs from the first of this month, last year.
        """
        t = datetime.date.today()
        return datetime.date(day=1, month=t.month, year=(t.year - 1))
    return None


DELTA = {
    QUICK_DATES.hour: datetime.timedelta(hours=1),
    QUICK_DATES.today: datetime.timedelta(days=1),
    QUICK_DATES.week: datetime.timedelta(days=7),
    QUICK_DATES.month: datetime.timedelta(days=31),
    QUICK_DATES.year: datetime.timedelta(days=366)
}


def first_letter(j):
    """Extract the first letter of a string"""
    # Defined as a method rather than using a lambda to keep a style guide happy.
    return j[0]


def get_permission_sqs(*args, **kwargs):
    psqs_kls = getattr(settings, 'ARISTOTLE_PERMISSION_SEARCH_CLASS', None)
    if psqs_kls is None:
        psqs_kls = PermissionSearchQuerySet
    else:
        psqs_kls = import_string(psqs_kls)
    return psqs_kls(*args, **kwargs)


class EmptyPermissionSearchQuerySet(EmptySearchQuerySet):
    # Just like a Haystack EmptySearchQuerySet, this behaves like a PermissionsSearchQuerySet
    # But returns nothing all the time.
    def apply_permission_checks(self, user=None, public_only=False, user_workgroups_only=False):
        return self

    def apply_registration_status_filters(self, *args, **kwargs):
        return self


class PermissionSearchQuerySet(SearchQuerySet):
    def models(self, *mods):
        # We have to redefine this because Whoosh & Haystack don't play well with model filtering
        from haystack.utils import get_model_ct
        mods = [get_model_ct(m) for m in mods]

        # This is performing a filter on the search result to restrict it to only the actual models
        return self.filter(django_ct__in=mods)

    def apply_permission_checks(self, user=None, public_only=False, user_workgroups_only=False):
        """"
        Apply permission checks by altering the SearchQuery
        """
        sqs = self
        q = SQ(is_public=True)
        q |= SQ(published_date_public__lte=timezone.now())
        if user is None or user.is_anonymous:
            # Regular users can only see public items, so filter only on the public items.
            sqs = sqs.filter(q)
            return sqs

        q |= SQ(submitter_id=user.pk)  # users can see items they create
        if user.is_superuser:
            q = SQ()  # Super-users can see everything
        else:
            # Non-registrars can only see public things or things in their workgroup
            # if they have no workgroups they won't see anything extra
            if user.profile.workgroups.count() > 0:
                # for w in user.profile.workgroups.all():
                #    q |= SQ(workgroup=str(w.id))
                q |= SQ(workgroup__in=[int(w.id) for w in user.profile.myWorkgroups.all()])
            if user.profile.is_registrar:
                # if registrar, also filter through items in the registered in their authorities
                q |= SQ(registrationAuthorities__in=[str(r.id) for r in user.profile.registrarAuthorities])
        if public_only:
            q &= SQ(is_public=True)
        if user_workgroups_only:
            q &= SQ(workgroup__in=[str(w.id) for w in user.profile.myWorkgroups.all()])

        if q:
            sqs = sqs.filter(q)
        return sqs

    def apply_registration_status_filters(self, states=[], ras=[]):
        """
        :param states:
        :param ras:
        :return: SearchQuerySet
        """
        sqs = self
        if states and not ras:
            states = [int(s) for s in states]
            sqs = sqs.filter(statuses__in=states)
        elif ras and not states:
            ras = [ra for ra in ras]
            sqs = sqs.filter(registrationAuthorities__in=ras)
        elif states and ras:
            # If we have both states and ras, merge them so we only search for
            # items with those statuses in those ras
            terms = ["%s___%s" % (str(r), str(s)) for r in ras for s in states]
            sqs = sqs.filter(ra_statuses__in=terms)
        return sqs


class TokenSearchForm(FacetedSearchForm):
    token_models: List[object] = []
    kwargs: Dict[str, str] = {}
    allowed_tokens = [
        'statuses',
        'highest_state',
        'name',
        'version',
        'identifier',
        'namespace',
        'uuid'
    ]

    token_shortnames = {
        'id': 'identifier',
        'ns': 'namespace',
        'hs': 'highest_state',
        'status': 'statuses',
    }

    def _clean_state(self, value):
        value = value.lower().strip(" ")
        if value in SHORT_STATE_MAP.keys():
            value = SHORT_STATE_MAP[value]
        return getattr(MDR.STATES, value.lower(), None)

    def process_highest_state(self, value):
        return self._clean_state(value)

    def process_statuses(self, values):
        return [
            self._clean_state(value)
            for value in values.split(",")
        ]

    def prepare_tokens(self):
        try:
            query = self.cleaned_data.get('q')
        except:
            # There was no query
            return {}
        opts = connections[DEFAULT_ALIAS].get_unified_index().fields.keys()
        kwargs = {}
        query_text = []
        token_models = []
        boost_ups = []
        for word in query.split(" "):
            # Boost the query words that start with +
            if word.startswith("+"):
                boost_strength = min(4, len(word) - len(word.lstrip('+')))
                boost_val = round(0.1 + 1.1 ** (boost_strength ** 1.35), 3)
                query_text.append(word)
                boost_ups.append((word.lstrip("+"), boost_val))
                continue

            word = word.replace("+", " ")
            if ":" in word:
                opt, arg = word.split(":", 1)

                # Make sure arg isnt blank
                if arg:
                    if opt in self.token_shortnames:
                        opt = self.token_shortnames[opt]

                    if opt in opts and opt in self.allowed_tokens:
                        clean_arguments_func = getattr(self, "process_%s" % opt, None)
                        if not clean_arguments_func:
                            kwargs[str(opt)]=arg
                        else:
                            # if we have a processor, run that.
                            clean_value = clean_arguments_func(arg)
                            if type(clean_value) is list:
                                kwargs["%s__in" % str(opt)] = clean_value
                            elif clean_value is not None:
                                kwargs[str(opt)] = clean_value
                    elif opt == "type":
                        # we'll allow these through and assume they meant content type
                        # Look up all the models that you can search from
                        from django.contrib.contenttypes.models import ContentType
                        arg = arg.lower().replace('_', '').replace('-', '')
                        app_labels = allowable_search_models()
                        mods = ContentType.objects.filter(app_label__in=app_labels).all()
                        for i in mods:
                            if hasattr(i.model_class(), 'get_verbose_name'):
                                model_short_code = "".join(
                                    map(
                                        first_letter, i.model_class()._meta.verbose_name.split(" ")
                                    )
                                ).lower()
                                if arg == model_short_code:
                                    token_models.append(i.model_class())
                            if arg == i.model:
                                token_models.append(i.model_class())

            else:
                query_text.append(word)
        self.token_models = token_models
        self.query_text = " ".join(query_text)
        self.kwargs = kwargs
        self.boost_ups = boost_ups
        return kwargs

    def search(self):
        self.query_text = None
        kwargs = self.prepare_tokens()
        if not self.is_valid():
            return self.no_query_found()

        if self.query_text:
            # If there is query text
            # Search on text (which is the document) and name fields (so name can be boosted)
            title_only = self.cleaned_data.get('title_only', None)
            if title_only:
                sqs = self.searchqueryset.filter(
                    SQ(name=AutoQuery(self.query_text))
                )
            else:
                sqs = self.searchqueryset.filter(
                    SQ(text=AutoQuery(self.query_text)) |
                    SQ(name=AutoQuery(self.query_text)) |
                    SQ(**{DJANGO_ID: self.query_text})
                )

        else:
            # Don't search
            sqs = self.searchqueryset

        if self.token_models:
            sqs = sqs.models(*self.token_models)
        if kwargs:
            sqs = sqs.filter(**kwargs)

        for word, boost_value in self.boost_ups:
            sqs = sqs.boost(word, boost_value)

        if self.load_all:
            sqs = sqs.load_all()

        # Only show models that are in apps that are enabled
        app_labels = allowable_search_models()
        # We need to restrict search so that if an install app is "disabled" by
        #    Aristotle, its models won't show up in search.
        sqs = sqs.filter(django_ct_app_label__in=app_labels)
        return sqs

    def no_query_found(self):
        return EmptyPermissionSearchQuerySet()


datePickerOptions = {
    "format": "YYYY-MM-DD",
    "defaultDate": "",
    "useCurrent": False,
}


class PermissionSearchForm(TokenSearchForm):
    """
        We need to make a new form as permissions to view objects are a bit finicky.
        This form allows us to perform the base query then restrict it to just those
        of interest.
    """
    # Use short names to reduce URL length
    mq=forms.ChoiceField(
        required=False,
        initial=QUICK_DATES.anytime,
        choices=QUICK_DATES,
        widget=BootstrapDropdownIntelligentDate
    )
    mds = forms.DateField(
        required=False,
        label="Modified after date",
        widget=BootstrapDateTimePicker(options=datePickerOptions)
    )
    mde = forms.DateField(
        required=False,
        label="Modified before date",
        widget=BootstrapDateTimePicker(options=datePickerOptions)
    )
    cq=forms.ChoiceField(
        required=False,
        initial=QUICK_DATES.anytime,
        choices=QUICK_DATES,
        widget=BootstrapDropdownIntelligentDate
    )
    cds = forms.DateField(
        required=False,
        label="Created after date",
        widget=BootstrapDateTimePicker(options=datePickerOptions)
    )
    cde = forms.DateField(
        required=False,
        label="Created before date",
        widget=BootstrapDateTimePicker(options=datePickerOptions)
    )

    ra = forms.MultipleChoiceField(
        required=False, label=_("Registration authority"),
        choices=[], widget=BootstrapDropdownSelectMultiple
    )
    sort = forms.ChoiceField(
        required=False, initial=SORT_OPTIONS.natural,
        choices=SORT_OPTIONS, widget=BootstrapDropdownSelect
    )

    from aristotle_mdr.search_indexes import BASE_RESTRICTION
    res = forms.ChoiceField(
        required=False, initial=None,
        choices=BASE_RESTRICTION.items(),
        label="Item visibility state"
    )

    state = forms.MultipleChoiceField(
        required=False,
        label=_("Registration status"),
        choices=MDR.STATES + [(-99, _('Unregistered'))],  # Allow unregistered as a selection
        widget=BootstrapDropdownSelectMultiple
    )
    public_only = forms.BooleanField(
        required=False,
        label="Only show public items"
    )
    title_only = forms.BooleanField(
        required=False,
        label="Search titles only"
    )
    myWorkgroups_only = forms.BooleanField(
        required=False,
        label="Only show items in my workgroups"
    )
    category = forms.ChoiceField(
        choices=SEARCH_CATEGORIES,
        required=False, label=_('Categories'),
        widget=BootstrapDropdownSelect
    )
    models = forms.MultipleChoiceField(
        choices=[],  # model_choices(),
        required=False, label=_('Item type'),
        widget=BootstrapDropdownSelectMultiple
    )
    rpp = forms.IntegerField(
        required=False,
        label='Results per page'
    )
    # Hidden Workgroup field that is not rendered in the template,
    # label is required for faceting display
    wg = forms.IntegerField(required=False,
                            label="Workgroup")
    # Hidden Stewardship Organisation field that is not rendered in the template,
    # label is required for faceting display
    sa = forms.IntegerField(required=False,
                            label="Stewardship Organisation")

    # Filters that are to be applied
    filters = ["models", "mq", "cq", "cds", "cde", "mds", "mde", "state", "ra", "res", "wg", "sa"]

    def __init__(self, *args, **kwargs):
        if 'searchqueryset' not in kwargs.keys() or kwargs['searchqueryset'] is None:
            kwargs['searchqueryset'] = get_permission_sqs()
        if not issubclass(type(kwargs['searchqueryset']), PermissionSearchQuerySet):
            raise ImproperlyConfigured("Aristotle Search Queryset connection must be a subclass of PermissionSearchQuerySet")
        super().__init__(*args, **kwargs)

        # Populate choice of Registration Authorities ordered by active state and name
        # Inactive last
        self.fields['ra'].choices = [(ra.id, ra.name) for ra in MDR.RegistrationAuthority.objects.filter(active__in=[0, 1]).order_by('active', 'name')]

        # List of models that you can search for

        self.default_models = [
            m[0] for m in model_choices()
            if m[0].split('.', 1)[0] in allowable_search_models()
        ]

        # Set choices for models
        self.fields['models'].choices = [
            m for m in model_choices()
            if m[0].split('.', 1)[0] in allowable_search_models()
        ]

    def get_models(self):
        """Return an alphabetical list of model classes in the index."""
        search_models = []

        if self.is_valid():
            app_labels = self.default_models
            if self.cleaned_data['models']:
                app_labels = self.cleaned_data['models']

            for model in app_labels:
                search_models.append(apps.get_model(*model.split('.')))

        return search_models

    @property
    def applied_filters(self):
        """
        Returns the filters appearing in the URL that are applied
        """
        if not hasattr(self, 'cleaned_data'):
            return []
        return [f for f in self.filters if self.cleaned_data.get(f, False)]

    def search(self, repeat_search=False):
        # First, store the SearchQuerySet received from other processing.
        sqs = super().search()

        # If we got an empty search queryset, no need for further processing
        if isinstance(sqs, EmptyPermissionSearchQuerySet):
            return sqs

        if not self.token_models and self.get_models():
            sqs = sqs.models(*self.get_models())
        self.repeat_search = repeat_search

        # Is there no filter and no query -> no search was performed
        has_filter = self.kwargs or self.token_models or self.applied_filters
        if not has_filter and not self.query_text:
            return self.no_query_found()

        if self.applied_filters and not self.query_text:
            # Set flag when filtering with no query (used in template)
            self.filter_search = True

        # Get filter data from query
        states = self.cleaned_data.get('state', None)
        ras = self.cleaned_data.get('ra', None)
        restriction = self.cleaned_data['res']
        search_category = self.cleaned_data['category']
        workgroup = self.cleaned_data.get('wg', None)
        stewardship_organisation = self.cleaned_data.get('sa', None)

        # Apply the filters
        sqs = sqs.apply_registration_status_filters(states, ras)
        if restriction:
            sqs = sqs.filter(restriction=restriction)

        if search_category and search_category != SEARCH_CATEGORIES.all:
            sqs = sqs.filter(category=search_category)

        sqs = self.apply_date_filtering(sqs)
        sqs = sqs.apply_permission_checks(
            user=self.request.user,
            public_only=self.cleaned_data['public_only'],
            user_workgroups_only=self.cleaned_data['myWorkgroups_only']
        )

        if workgroup is not None:
            # We don't want to filter on a non-existent field
            # Must filter exactly
            sqs = sqs.filter(workgroup__exact=workgroup)

        if stewardship_organisation is not None:
            # Apply the stewardship organisation filter
            sqs = sqs.filter(stewardship_organisation=stewardship_organisation)

        # f for facets
        extra_facets_details = {}
        facets_opts = self.request.GET.getlist('f', [])

        for _facet in facets_opts:
            _facet, value = _facet.split("::", 1)
            # Force exact as otherwise we don't match when there are spaces.
            sqs = sqs.filter(**{"%s__exact" % _facet: value})
            facets_details = extra_facets_details.get(_facet, {'applied': []})
            facets_details['applied'] = list(set(facets_details['applied'] + [value]))
            extra_facets_details[_facet] = facets_details

        self.has_spelling_suggestions = False
        if not self.repeat_search:

            if sqs.count() < 5:
                self.check_spelling(sqs)

            if sqs.count() == 0:
                if sqs.count() == 0 and self.has_spelling_suggestions:
                    self.auto_correct_spell_search = True
                    self.cleaned_data['q'] = self.suggested_query
                elif has_filter and self.cleaned_data['q']:
                    # If there are 0 results with a search term, and filters applied
                    # lets be nice and remove the filters and try again.
                    # There will be a big message on the search page that says what we did.
                    for f in self.filters:
                        self.cleaned_data[f] = None
                    self.auto_broaden_search = True
                # Re run the query with the updated details
                sqs = self.search(repeat_search=True)
            # Only apply sorting on the first pass through
            sqs = self.apply_sorting(sqs)

        # Don't applying sorting on the facet as ElasticSearch2 doesn't like this.
        filters_to_facets = {
            'ra': 'registrationAuthorities',
            'models': 'facet_model_ct',
            'state': 'statuses',
        }

        # Add filters that are also facets to Search Query Set
        for _filter, facet in filters_to_facets.items():
            if _filter not in self.applied_filters:
                sqs = sqs.facet(facet)

        logged_in_facets = {
            'wg': 'workgroup',
            'res': 'restriction'
        }

        # If user is logged in, add permisssioned facets to Search Query Set
        if self.request.user.is_active:
            for _filter, facet in logged_in_facets.items():
                if _filter not in self.applied_filters:
                    # Don't do this: sqs = sqs.facet(facet, sort='count')
                    sqs = sqs.facet(facet)

        # For facets that will always appear on the sidebar, but are not part of the previous lists
        additional_hardcoded_facets = ['stewardship_organisation']
        for facet in additional_hardcoded_facets:
            sqs = sqs.facet(facet)

        # Generate details about facets from ``concepts`` registered (as facetable) with a Haystack search index that conforms
        # to Aristotle permissions. Excludes facets that have been previously been added.
        extra_facets = []
        from aristotle_mdr.search_indexes import registered_indexes
        for model_index in registered_indexes:
            for name, field in model_index.fields.items():
                if field.faceted:
                    if name not in (list(filters_to_facets.values()) + list(logged_in_facets.values()) +
                                    additional_hardcoded_facets):
                        extra_facets.append(name)

                        x = extra_facets_details.get(name, {})
                        x.update({
                            'title': getattr(field, 'title', name),
                            'display': getattr(field, 'display', None),
                            'allow_search': getattr(field, 'allow_search', False),
                        })
                        extra_facets_details[name]= x
                        # Don't do this: sqs = sqs.facet(facet, sort='count')  # Why Sam, why?
                        sqs = sqs.facet(name)

        # Generate facet content
        self.facets = sqs.facet_counts()

        # Populate the extra facet fields
        if 'fields' in self.facets:
            self.extra_facet_fields = [
                (k, {'values': sorted(v, key=lambda x: -x[1])[:10], 'details': extra_facets_details[k]})
                for k, v in self.facets['fields'].items()
                if k in extra_facets
            ]

            self.extra_facet_fields = [
                (k, {
                    'values': [
                        f for f in
                        sorted(v, key=lambda x: -x[1])
                        if f[0] not in extra_facets_details.get(k, {}).get('applied', [])
                        ][:10],
                    'details': extra_facets_details[k]
                })
                for k, v in self.facets['fields'].items()
                if k in extra_facets
            ]

            # Cut down to only the top 10 results for each facet, order by number of results
            for facet, counts in self.facets['fields'].items():
                self.facets['fields'][facet] = sorted(counts, key=lambda x: -x[1])[:10]

            # Perform id to object lookup
            from django.contrib.contenttypes.models import ContentType
            model_types = {
                'stewardship_organisation': MDR.StewardOrganisation,
                'registrationAuthorities': MDR.RegistrationAuthority,
                'workgroup': MDR.Workgroup,
                'facet_model_ct': ContentType,
            }

            for facet in self.facets['fields'].keys():
                if facet in model_types.keys():
                    id_to_item = {}
                    # Facet is for a model that must be looked up from the database
                    item_type = model_types.get(facet)
                    ids = []
                    for id, count in self.facets['fields'][facet]:
                        if id is not None:
                            ids.append(id)

                    id_to_instance = item_type.objects.in_bulk(ids)

                    for id, count in self.facets['fields'][facet]:
                        if id is None:
                            id_to_item[id] = (None, count)
                        # TODO: eradicate -99 from code
                        elif (id == -99):
                            id_to_item[id] = (None, count)

                        else:
                            id_to_item[id] = (id_to_instance[int(id)], count)
                    self.facets['fields'][facet] = id_to_item

        return sqs

    def check_spelling(self, sqs):
        if self.query_text:
            original_query = self.cleaned_data.get('q', "")

            from urllib.parse import quote_plus

            suggestions = []
            has_suggestions = False
            suggested_query = []

            # lets assume the words are ordered in importance
            # So we suggest words in order
            optimal_query = original_query
            for token in self.cleaned_data.get('q', "").split(" "):
                if token:  # remove blanks
                    suggestion = self.searchqueryset.spelling_suggestion(token)
                    if suggestion:
                        test_query = optimal_query.replace(token, suggestion)
                        # Haystack can *over correct* so we'll do a quick search with the
                        # suggested spelling to compare words against
                        try:
                            self.searchqueryset.auto_query(test_query)[0]
                            suggested_query.append(suggestion)
                            has_suggestions = True
                            optimal_query = test_query
                        except:
                            suggestion = None
                    else:
                        suggested_query.append(token)
                    suggestions.append((token, suggestion))

            if optimal_query != original_query:
                if optimal_query == original_query.lower():
                    # If the suggested query is the same query but in lowercase, don't suggest it
                    self.has_spelling_suggestions = False
                else:
                    self.spelling_suggestions = suggestions
                    self.has_spelling_suggestions = has_suggestions
                    self.original_query = self.cleaned_data.get('q')
                    self.suggested_query = quote_plus(' '.join(suggested_query), safe="")

    def apply_date_filtering(self, sqs):
        modify_quick_date = self.cleaned_data['mq']
        create_quick_date = self.cleaned_data['cq']
        create_date_start = self.cleaned_data['cds']
        create_date_end = self.cleaned_data['cde']
        modify_date_start = self.cleaned_data['mds']
        modify_date_end = self.cleaned_data['mde']

        """
        Modified filtering is really hard to do formal testing for as the modified
        dates are altered on save, so its impossible to alter the modified dates
        to check the search is working.
        However, this is the exact same process as creation date (which we can alter),
        so if creation filtering is working, modified filtering should work too.
        """
        if modify_quick_date and modify_quick_date is not QUICK_DATES.anytime:  # pragma: no cover
            delta = time_delta(modify_quick_date)
            if delta is not None:
                sqs = sqs.filter(modifed__gte=delta)
        elif modify_date_start or modify_date_end:  # pragma: no cover
            if modify_date_start:
                sqs = sqs.filter(modifed__gte=modify_date_start)
            if modify_date_end:
                sqs = sqs.filter(modifed__lte=modify_date_end)

        if create_quick_date and create_quick_date is not QUICK_DATES.anytime:
            delta = time_delta(create_quick_date)
            if delta is not None:
                sqs = sqs.filter(created__gte=delta)
        elif create_date_start or create_date_end:
            if create_date_start:
                sqs = sqs.filter(created__gte=create_date_start)
            if create_date_end:
                sqs = sqs.filter(created__lte=create_date_end)

        return sqs

    def apply_sorting(self, sqs):  # pragma: no cover, no security issues, standard Haystack methods, so already tested.

        sort_order = self.cleaned_data['sort']

        # Ordering is evaluated from left to right
        if sort_order == SORT_OPTIONS.modified_ascending:
            sqs = sqs.order_by('modified', 'name_sortable')

        elif sort_order == SORT_OPTIONS.modified_descending:
            sqs = sqs.order_by('-modified', 'name_sortable')

        elif sort_order == SORT_OPTIONS.created_ascending:
            sqs = sqs.order_by('created', 'name_sortable')

        elif sort_order == SORT_OPTIONS.created_descending:
            sqs = sqs.order_by('-created', 'name_sortable')

        elif sort_order == SORT_OPTIONS.alphabetical:
            sqs = sqs.order_by('name_sortable')

        elif sort_order == SORT_OPTIONS.state:
            sqs = sqs.order_by('-highest_state', 'name_sortable')

        return sqs
