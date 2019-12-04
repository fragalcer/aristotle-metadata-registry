import reversion
import json
import logging
from typing import List, Dict, Any
from django.conf import settings

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect, get_object_or_404

from django.utils.module_loading import import_string
from django.utils import timezone
from django.forms import modelformset_factory
from django.urls import reverse

from django.views.generic import (
    DetailView,
    TemplateView,
    CreateView,
    UpdateView
)
from django_bulk_update.helper import bulk_update

from aristotle_mdr import models as MDR
from aristotle_mdr import perms
from aristotle_mdr.forms.forms import ReviewChangesForm
from aristotle_mdr.utils import cascade_items_queryset, get_status_change_details, get_cascaded_ids
from aristotle_mdr.views import ReviewChangesView, display_review
from aristotle_mdr.views.utils import (
    generate_visibility_matrix,
    paginated_list,
    UserFormViewMixin,
    FormsetView
)
from aristotle_bg_workers.tasks import register_items
from aristotle_bg_workers.utils import run_task_on_commit

from . import models, forms


logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


@login_required
def my_review_list(request):
    # Users can see any items they have been asked to review
    q = Q(requester=request.user)
    reviews = models.ReviewRequest.objects.visible(request.user).filter(q).filter(registration_authority__active=0)
    return paginated_list(request, reviews, "aristotle_mdr/reviews/my_review_list.html", {'reviews': reviews})


@login_required
def review_list(request):
    if not request.user.profile.is_registrar:
        raise PermissionDenied
    authorities = [i[0] for i in request.user.profile.registrarAuthorities.filter(active=0).values_list('id')]

    # Registrars can see items they have been asked to review
    q = Q(Q(registration_authority__id__in=authorities) & ~Q(status=models.REVIEW_STATES.revoked))

    reviews = models.ReviewRequest.objects.visible(request.user).filter(q)
    return paginated_list(request, reviews, "aristotle_mdr/reviews/reviewers_review_list.html", {'reviews': reviews})


class ReviewActionMixin(LoginRequiredMixin, UserFormViewMixin):
    """Mixin used for functionality common to all review tabs"""
    pk_url_kwarg = 'review_id'
    context_object_name = "review"
    user_form = True
    perm_function = 'user_can_view_review'

    def dispatch(self, *args, **kwargs):
        self.review = self.get_review()
        self.review_concepts = self.review.concepts.all()

        perm_func = getattr(perms, self.perm_function)
        if not perm_func(self.request.user, self.review):
            if self.request.user.is_anonymous:
                return redirect(reverse('friendly_login') + '?next=%s' % self.request.path)
            else:
                raise PermissionDenied

        return super().dispatch(*args, **kwargs)

    def get_review(self):
        return get_object_or_404(models.ReviewRequest, pk=self.kwargs['review_id'])

    def get_supersedes_qs(self):
        return MDR.SupersedeRelationship.objects.filter(
            newer_item__in=self.review_concepts,
            registration_authority=self.review.registration_authority
        ).select_related('older_item', 'newer_item')

    def get_supersedes_context(self) -> List[Dict[str, Dict[str, Any]]]:
        supersedes = []
        qs = self.get_supersedes_qs()
        for supersede in qs:
            supersedes.append({
                'older': {'id': supersede.older_item.id, 'name': supersede.older_item.name},
                'newer': {'id': supersede.newer_item.id, 'name': supersede.newer_item.name},
                'message': supersede.message,
                'date_effective': supersede.date_effective
            })
        return supersedes

    def get_context_data(self, *args, **kwargs):
        kwargs = super().get_context_data(*args, **kwargs)
        kwargs.update({
            'review': self.review,
            'can_approve_review': perms.user_can_approve_review(self.request.user, self.review),
            'can_open_close_review': perms.user_can_close_or_reopen_review(self.request.user, self.review),
            'can_edit_review': perms.user_can_edit_review(self.request.user, self.review),
            'is_registrar': perms.user_is_registrar(self.request.user)
        })
        if hasattr(self, "active_tab_name"):
            kwargs['active_tab'] = self.active_tab_name

        if self.review.concepts.count() == 1:
            # It's for a single item review, display in breadcrumbs
            kwargs.update({
                'single_item_review': True,
                'item_under_review': self.review.concepts.first()
            })
        return kwargs

    def get_object(self):
        return self.review


class ReviewDetailsView(ReviewActionMixin, DetailView):
    template_name = "aristotle_mdr/reviews/review/details.html"
    active_tab_name = "details"

    def get_context_data(self, *args, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(*args, **kwargs)
        # context['next'] = self.request.GET.get('next', reverse('aristotle_reviews:userReadyForReview'))
        context['can_accept_review'] = self.review.status == models.REVIEW_STATES.open and perms.user_can_approve_review(self.request.user, self.review)
        context['dynamic_open_close'] = True
        return context


class ReviewUpdateView(ReviewActionMixin, UpdateView):
    template_name = "aristotle_mdr/reviews/review/update.html"
    form_class = forms.RequestReviewUpdateForm
    context_object_name = "item"
    model = models.ReviewRequest
    user_form = True
    perm_function = 'user_can_edit_review'

    def get_success_url(self):
        return self.get_review().get_absolute_url()


class ReviewCreateView(UserFormViewMixin, CreateView):
    template_name = "aristotle_mdr/reviews/review/create.html"
    form_class = forms.RequestReviewCreateForm
    model = models.ReviewRequest
    user_form = True

    def get_initial(self):
        initial = super().get_initial()

        item_ids = self.request.GET.getlist("items")
        initial_metadata = MDR._concept.objects.visible(self.request.user).filter(id__in=item_ids)
        initial.update({
            "concepts": initial_metadata,
        })

        return initial

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.requester = self.request.user
        return super().form_valid(form)


class ReviewStatusChangeBase(ReviewActionMixin, ReviewChangesView):
    """Base view for status changing"""

    change_step_name = 'review_accept'

    condition_dict = {'review_changes': display_review}
    display_review = None
    review = None
    user_form = True
    show_supersedes: bool = True
    message = 'Items have been registered'

    def dispatch(self, request, *args, **kwargs):

        review = self.get_review()

        if not self.ra_active_check(review):
            raise Http404

        if not perms.user_can_approve_review(self.request.user, review):
            raise PermissionDenied
        if review.status != models.REVIEW_STATES.open:
            messages.add_message(self.request, messages.WARNING, "This review is already closed. Re-open this review to endorse content.")
            return HttpResponseRedirect(reverse('aristotle_reviews:review_details', args=[review.pk]))

        return super().dispatch(request, *args, **kwargs)

    def ra_active_check(self, review):
        return review.registration_authority.is_active

    def get_items(self):
        return self.review_concepts

    def get_change_data(self, register=False):
        review = self.get_review()

        # Register status changes
        change_data = {
            'registrationAuthorities': [review.registration_authority],
            'state': review.target_registration_state,
            'registrationDate': review.registration_date,
            'cascadeRegistration': review.cascade_registration,
            'changeDetails': self.get_cleaned_data_for_step(self.change_step_name)['status_message']
        }

        if register:
            # If registering cascade needs to be a boolean
            # This is done automatically on clean for the change status forms
            change_data['cascadeRegistration'] = (review.cascade_registration == 1)

        return change_data

    def get_context_data(self, *args, **kwargs):
        review = self.get_review()
        kwargs = super().get_context_data(*args, **kwargs)
        kwargs['status_matrix'] = json.dumps(generate_visibility_matrix(self.request.user))
        kwargs['review'] = review
        kwargs['ra'] = review.registration_authority
        if self.show_supersedes:
            kwargs['supersedes'] = self.get_supersedes_context()
        kwargs['show_supersedes'] = self.show_supersedes
        return kwargs

    def get_form_kwargs(self, step):

        kwargs = super().get_form_kwargs(step)

        if step == 'review_accept':
            return {'user': self.request.user}

        return kwargs


class ReviewAcceptView(ReviewStatusChangeBase):
    """Accept the review at the proposed status level"""

    form_list = [
        ('review_accept', forms.RequestReviewAcceptForm),
        ('review_changes', ReviewChangesForm)
    ]

    templates = {
        'review_accept': 'aristotle_mdr/user/user_request_accept.html',
        'review_changes': 'aristotle_mdr/actions/review_state_changes.html'
    }

    def approve_supersedes(self, review, reg_date):
        sups = review.proposed_supersedes

        old_items = [s.older_item.id for s in sups]

        if not reg_date:
            reg_date = timezone.now().date()

        # Set all old items to the Superseded status
        register_args=[
            old_items,
            False,
            MDR.STATES.superseded,
            review.registration_authority_id,
            self.request.user.id,
            "",
            (reg_date.year, reg_date.month, reg_date.day),
            False
        ]

        # Run as celery task unless always sync
        if settings.ALWAYS_SYNC_REGISTER:
            register_items(*register_args)
        else:
            run_task_on_commit(
                register_items,
                args=register_args
            )

        # Approve all proposed supersedes
        sups.update(proposed=False)

    def done(self, form_list, **kwargs):

        review = self.get_review()
        form_dict = kwargs.get('form_dict')

        with reversion.revisions.create_revision():
            self.register_changes(kwargs.get('form_dict'))

            if form_dict['review_accept'].cleaned_data['close_review'] == "1":
                review.status = models.REVIEW_STATES.approved
                review.save()

            # Add to status change timeline
            models.ReviewStatusChangeTimeline.objects.create(
                request=review, status=models.REVIEW_STATES.approved,
                actor=self.request.user
            )
            # Add to review endorsement timeline
            models.ReviewEndorsementTimeline.objects.create(
                request=review,
                registration_state=review.target_registration_state,
                actor=self.request.user
            )

            # Approve supersedes
            cleaned_data = self.get_change_data()
            regDate = cleaned_data['registrationDate']
            self.approve_supersedes(review, regDate)

            messages.add_message(self.request, messages.INFO, self.message)

        return HttpResponseRedirect(reverse('aristotle_reviews:review_details', args=[review.pk]))


class ReviewEndorseView(ReviewStatusChangeBase):
    """Accept the review at a new status level"""

    form_list = [
        ('review_accept', forms.RequestReviewEndorseForm),
        ('review_changes', ReviewChangesForm)
    ]

    templates = {
        'review_accept': 'aristotle_mdr/user/user_request_endorse.html',
        'review_changes': 'aristotle_mdr/actions/review_state_changes.html'
    }

    show_supersedes = False

    def get_change_data(self, register=False):
        change_data = super().get_change_data(register)
        change_data['state'] = int(self.get_cleaned_data_for_step(self.change_step_name)['registration_state'])
        change_data['registrationDate'] = self.get_cleaned_data_for_step(self.change_step_name)['registration_date']
        cascade = self.get_cleaned_data_for_step(self.change_step_name)['cascade_registration']

        try:
            cascade = int(cascade)
        except:
            cascade = 0

        change_data['cascadeRegistration'] = cascade
        return change_data

    def done(self, form_list, **kwargs):

        review = self.get_review()
        form_dict = kwargs.get('form_dict')

        with reversion.revisions.create_revision():
            self.register_changes(form_dict)

            if int(form_dict['review_accept'].cleaned_data['close_review']) == 1:
                review.status = models.REVIEW_STATES.closed
                review.save()

            models.ReviewEndorsementTimeline.objects.create(
                request=review,
                registration_state=self.get_cleaned_data_for_step(self.change_step_name)['registration_state'],
                actor=self.request.user
            )

            messages.add_message(self.request, messages.INFO, self.message)

        return HttpResponseRedirect(reverse('aristotle_reviews:review_details', args=[review.pk]))


class ReviewIssuesView(ReviewActionMixin, TemplateView):
    pk_url_kwarg = 'review_id'
    template_name = "aristotle_mdr/reviews/review/issues.html"
    context_object_name = "review"
    active_tab_name = "issues"

    def get_context_data(self, *args, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(*args, **kwargs)

        from aristotle_mdr.contrib.issues.models import Issue
        base_qs = Issue.objects.filter(item__rr_review_requests=self.get_review())
        context['open_issues'] = base_qs.filter(isopen=True).order_by('created')
        context['closed_issues'] = base_qs.filter(isopen=False).order_by('created')

        return context


class ReviewListItemsView(ReviewActionMixin, DetailView):
    template_name = "aristotle_mdr/reviews/review/list.html"
    active_tab_name = "itemlist"

    def get_context_data(self, *args, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(*args, **kwargs)
        context['next'] = self.request.GET.get('next', reverse('aristotle_reviews:userReadyForReview'))

        review = self.get_review()

        concepts = []
        cascaded_ids = get_cascaded_ids(items=review.concepts.all())

        for concept in review.concepts.all():
            if concept.id in cascaded_ids:
                # Concept was added as a cascade
                concepts.append({'item': concept, 'remove': False})
            else:
                concepts.append({'item': concept, 'remove': True})

        context['concepts'] = concepts

        return context


class ReviewImpactView(ReviewActionMixin, TemplateView):
    pk_url_kwarg = 'review_id'
    template_name = "aristotle_mdr/reviews/review/impact.html"
    context_object_name = "review"
    active_tab_name = "impact"

    def get_context_data(self, *args, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(*args, **kwargs)
        review = self.get_review()

        if review.cascade_registration:
            # Get the affected items
            queryset = cascade_items_queryset(items=review.concepts.all())
        else:
            # Get all related items
            queryset = review.concepts.all()
        extra_info, any_higher = get_status_change_details(queryset, review.registration_authority, review.state)

        for concept in queryset:
            concept.info = extra_info[concept.id]

        context['statuses'] = queryset

        return context


class ReviewSupersedesEditView(ReviewActionMixin, FormsetView):
    pk_url_kwarg = 'review_id'
    template_name = "aristotle_mdr/reviews/review/supersedes.html"
    context_object_name = "review"
    active_tab_name = "supersedes"
    user_form = True
    perm_function = 'user_can_edit_review'

    def get_formset_class(self):
        return modelformset_factory(
            MDR.SupersedeRelationship,
            form=forms.ReviewRequestSupersedesForm,
            formset=forms.ReviewRequestSupersedesFormset,
            extra=1,
            can_delete=True,
        )

    def get_formset_kwargs(self):
        kwargs = super().get_formset_kwargs()
        kwargs['queryset'] = self.get_supersedes_qs()
        return kwargs

    def get_formset(self):
        formset = super().get_formset()
        # Pass review concepts through to form
        formset.form_kwargs['review_concepts'] = self.review_concepts
        formset.form_kwargs['user'] = self.request.user

        # Get data attrs
        review_items = self.review_concepts.select_subclasses()
        widget_data = {
            'data-label': {i.pk: type(i)._meta.label_lower for i in review_items}
        }
        formset.form_kwargs['widget_data'] = widget_data
        return formset

    def formset_valid(self, formset):
        # Save but dont commit so _objects properties are set
        formset.save(commit=False)
        # Get lists of objects
        updated = [n[0] for n in formset.changed_objects]
        created = formset.new_objects
        deleted = formset.deleted_objects

        for ss in created:
            # Set data not available through form
            ss.proposed = True
            ss.registration_authority = self.review.registration_authority
            ss.review = self.review

        if created:
            # Bulk save created
            MDR.SupersedeRelationship.objects.bulk_create(created)
        if updated:
            # Bulk save updated
            bulk_update(updated, batch_size=500)
        if deleted:
            # Bulk delete
            ids = [i.id for i in deleted]
            MDR.SupersedeRelationship.proposed_objects.filter(id__in=ids).delete()

        # Redirect to supersedes info page
        return HttpResponseRedirect(
            reverse('aristotle_reviews:request_supersedes', args=[self.review.id])
        )


class ReviewSupersedesInfoView(ReviewActionMixin, TemplateView):
    pk_url_kwarg = 'review_id'
    template_name = "aristotle_mdr/reviews/review/supersedes_info.html"
    context_object_name = "review"
    active_tab_name = "supersedes"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['supersedes'] = self.get_supersedes_context()
        context['can_edit_review'] = perms.user_can_edit_review(self.request.user, self.review)
        return context


class ReviewValidationView(ReviewActionMixin, TemplateView):
    pk_url_kwarg = 'review_id'
    template_name = "aristotle_mdr/reviews/review/validation.html"
    context_object_name = "review"
    active_tab_name = "checks"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        review = self.get_review()
        items = review.concepts.all().select_subclasses()

        review_items: List = list(items)
        if review.cascade_registration == 1:
            sub_items = []
            for item in items:
                sub_items += item.registry_cascade_items
            review_items += sub_items

        runner_class = import_string(settings.ARISTOTLE_VALIDATION_RUNNER)
        self.ra = self.get_review().registration_authority

        runner = runner_class(registration_authority=self.ra, state=self.get_review().state)
        total_results = runner.validate_metadata(metadata=review_items)

        context['no_results'] = not bool([result['results'] for result in total_results if result['results']])
        context['total_results'] = total_results
        context['setup_valid'] = True

        return context
