from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.generic import FormView

from aristotle_mdr import exceptions as registry_exceptions
from aristotle_mdr.utils import fetch_aristotle_settings
from aristotle_mdr.views import ReviewChangesView, display_review
from aristotle_mdr.forms.forms import ReviewChangesForm
from aristotle_mdr.forms.bulk_actions import ChangeStateForm


class BulkAction(FormView):

    def dispatch(self, *args, **kwargs):
        action = self.get_action()
        if not action:
            return HttpResponseRedirect(self.request.GET.get("next", "/"))
        if not action['can_use'](self.request.user):
            if self.request.user.is_anonymous:
                return redirect(
                    reverse('friendly_login') + '?next=%s' % self.request.path
                )
            else:
                raise PermissionDenied
        return super().dispatch(*args, **kwargs)

    def get_action(self):
        actions = get_bulk_actions()
        action = self.request.POST.get("bulkaction", None)
        return actions.get(action, None)

    def post(self, request, *args, **kwargs):
        url = request.GET.get("next", reverse("aristotle:home"))
        action = self.get_action()

        if action is None:
            # no action, messed up, redirect
            return HttpResponseRedirect(url)
        action_form = action['form']

        if action_form.redirect:
            return HttpResponseRedirect(action_form.get_redirect_url(request))

        if issubclass(action_form, ChangeStateForm):
            # If the form is a change state form
            # Put the items into the users session and redirect

            items_list = self.request.POST.getlist('items')
            if items_list:
                self.request.session['bulkaction_items'] = items_list
            else:
                if 'bulkaction_items' in self.request.session:
                    del self.request.session['bulkaction_items']

            self.request.session['next'] = url

            return HttpResponseRedirect(reverse('aristotle:change_state_bulk_action'))

        if action_form.confirm_page is None:
            # if there is no confirm page or extra details required, do the action and redirect
            form = action_form(request.POST, user=request.user, request=request)  # A form bound to the POST data

            if form.is_valid():
                to_change = form.items_to_change

                confirmed = request.POST.get("confirmed", None)
                if to_change.count() > 10 and not confirmed:
                    new_form = request.POST.copy()
                    new_form.setlist('items', form.items_to_change.values_list('id', flat=True))
                    form = action_form(new_form, user=request.user, request=request, items=[])
                    return render(
                        request,
                        "aristotle_mdr/actions/bulk_actions/lots_of_things.html",
                        {
                            "items": to_change,
                            "form": form,
                            "next": url,
                            "action": action,
                        }
                    )
                message = form.make_changes()
                messages.add_message(request, messages.INFO, message)
            else:
                messages.add_message(request, messages.ERROR, form.errors)
            return HttpResponseRedirect(url)
        else:
            form = action_form(request.POST, user=request.user, request=request)
            items = []
            if form.is_valid():
                items = form.cleaned_data['items']

            confirmed = request.POST.get("confirmed", None)
            if form.items_to_change:
                new_form = request.POST.copy()
                new_form.setlist('items', form.items_to_change.values_list('id', flat=True))
                request.POST = new_form

            if confirmed:
                # We've passed the confirmation page, try and save.
                form = action_form(request.POST, user=request.user, request=request, items=items)  # A form bound to the POST data
                # there was an error with the form redisplay
                if form.is_valid():
                    message = form.make_changes()

                    messages.add_message(request, messages.INFO, message)
                    return HttpResponseRedirect(url)
            else:
                # we need a confirmation, render the next form
                form = action_form(form=None, initial=dict(request.POST), user=request.user, request=request, items=items)

            return render(
                request,
                action_form.confirm_page,
                {
                    "items": items,
                    "form": form,
                    "next": url,
                    "action": action,
                    "bulk_action_title": self.request.POST.get("bulkaction", None)
                }
            )


def get_bulk_actions():
    import re
    config = fetch_aristotle_settings()

    actions = {}
    for action_name in config.get('BULK_ACTIONS', []):
        if not re.search(r'^[a-zA-Z0-9\_\.]+$', action_name):  # pragma: no cover
            # Invalid download_type
            raise registry_exceptions.BadBulkActionModuleName("Bulk action isn't a valid Python module name.")

        from django.utils.module_loading import import_string

        f = import_string(action_name)
        # We need to make this a dictionary, not a class as otherwise
        # the template engine tries to instantiate it.
        frm = {'form': f}
        for prop in ['classes', 'can_use', 'text']:
            frm[prop] = getattr(f, prop, None)
        actions[action_name] = frm
    return actions


class ChangeStatusBulkActionView(ReviewChangesView):

    change_step_name = 'change_state'

    form_list = [
        ('change_state', ChangeStateForm),
        ('review_changes', ReviewChangesForm)
    ]

    templates = {
        'change_state': 'aristotle_mdr/actions/bulk_actions/change_status.html',
        'review_changes': 'aristotle_mdr/actions/review_state_changes.html'
    }

    condition_dict = {'review_changes': display_review}
    display_review = None

    def get_items(self):
        return self.get_change_data()['items']

    def get_form_kwargs(self, step):

        kwargs = super().get_form_kwargs(step)

        if step == 'change_state':
            kwargs.update({'user': self.request.user, 'form': None, 'request': self.request})

        return kwargs

    def get_form_initial(self, step):

        initial = super().get_form_initial(step)

        if step == 'change_state':
            if 'bulkaction_items' in self.request.session:
                bulk_items = self.request.session['bulkaction_items']
                initial.update({'items': bulk_items})

        return initial

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        if 'next' in self.request.session:
            context.update({'next': self.request.session['next']})

        return context

    def done(self, form_list, form_dict, **kwargs):

        self.register_changes(form_dict, 'change_state')

        if 'next' in self.request.session:
            url = self.request.session['next']
        else:
            url = '/'
        return HttpResponseRedirect(url)
