from django.contrib import messages

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _

from django.http import Http404

from aristotle_mdr import models as MDR
from aristotle_mdr import forms as MDRForms
from aristotle_mdr import perms
from aristotle_mdr.views.utils import ObjectLevelPermissionRequiredMixin

from braces.views import LoginRequiredMixin
from django.views.generic import DeleteView, TemplateView, FormView, UpdateView
from aristotle_mdr.contrib.generic.views import ConfirmDeleteView


class All(LoginRequiredMixin, TemplateView):
    # Show all discussions for all of a users workgroups
    template_name = "aristotle_mdr/discussions/all.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['discussions'] = self.request.user.profile.discussions

        return context


class Workgroup(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, TemplateView):
    # Show all discussions for a workgroups
    template_name = "aristotle_mdr/discussions/workgroup.html"
    permission_required = "aristotle_mdr.can_view_discussions_in_workgroup"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        wg = get_object_or_404(MDR.Workgroup, pk=self.kwargs['wgid'])

        if not perms.user_in_workgroup(request.user, wg):
            raise PermissionDenied

        context['workgroup'] = wg
        context['discussions'] = wg.discussions.all()

        return render(request, self.template_name, context)

    def check_permissions(self, request):
        """
        Returns whether or not the user has permissions
        """
        wg = get_object_or_404(MDR.Workgroup, pk=self.kwargs['wgid'])
        return request.user.has_perm(self.get_permission_required(request), wg)


class New(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, FormView):
    permission_required = "aristotle_mdr.can_post_discussion_in_workgroup"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get_permission_required(self, request):
        wg_pk = request.GET.get('workgroup')
        if request.user.profile.myWorkgroups.filter(pk=wg_pk).exists():
            return "aristotle_mdr.can_post_discussion_in_workgroup"
        else:
            return "aristotle_mdr.can_post_discussion"

    def get_object(self):
        wg_pk = self.request.GET.get('workgroup')
        return self.request.user.profile.myWorkgroups.filter(pk=wg_pk).first()

    def post(self, request, *args, **kwargs):
        # If the form has been submitted...
        form = MDRForms.discussions.NewPostForm(request.POST, user=request.user)  # A form bound to the POST data
        if form.is_valid():
            # process the data in form.cleaned_data as required
            new = MDR.DiscussionPost(
                workgroup=form.cleaned_data['workgroup'],
                title=form.cleaned_data['title'],
                body=form.cleaned_data['body'],
                author=request.user,
            )
            new.save()

            new.relatedItems.set(form.cleaned_data['relatedItems'])

            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[new.pk]))

        return render(request, "aristotle_mdr/discussions/new.html", {"form": form})

    def get(self, request, *args, **kwargs):
        initial = {}
        if request.GET.get('workgroup'):
            if request.user.profile.myWorkgroups.filter(id=request.GET.get('workgroup')).exists():
                initial={'workgroup': request.GET.get('workgroup')}
            else:
                # If a user tries to navigate to a page to post
                # to a workgroup they aren't in, redirect them to the regular post page.
                return HttpResponseRedirect(reverse("aristotle:discussionsNew"))
            if request.GET.getlist('item'):
                workgroup = request.user.profile.myWorkgroups.get(id=request.GET.get('workgroup'))
                items = request.GET.getlist('item')
                initial.update({'relatedItems': workgroup.items.filter(id__in=items)})

        form = MDRForms.discussions.NewPostForm(user=request.user, initial=initial)

        return render(request, "aristotle_mdr/discussions/new.html", {"form": form})


class PostMixin(object):
    def get_object(self):
        return get_object_or_404(MDR.DiscussionPost, pk=self.kwargs['pid'])


class Post(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, PostMixin, TemplateView):
    template_name = "aristotle_mdr/discussions/post.html"
    permission_required = "aristotle_mdr.can_view_discussion_post"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get(self, request, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        post = self.get_object()

        if not perms.user_in_workgroup(request.user, post.workgroup):
            raise PermissionDenied
        comment_form = MDRForms.discussions.CommentForm(initial={
            'post': self.kwargs['pid']
        })

        context['workgroup'] = post.workgroup
        context['post'] = post
        context['comment_form'] = comment_form

        return render(request, self.template_name, context)


class TogglePost(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, PostMixin, TemplateView):
    permission_required = "aristotle_mdr.user_can_alter_post"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get(self, request, *args, **kwargs):
        post = self.get_object()
        post.closed = not post.closed
        post.save()

        return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))


class NewComment(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, PostMixin, FormView):
    permission_required = "aristotle_mdr.can_comment_on_post"
    raise_exception = True
    redirect_unauthenticated_users = True

    def post(self, request, *args, **kwargs):
        post = self.get_object()

        if post.closed:
            messages.error(request, _('This post is closed. Your comment was not added.'))
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))

        form = MDRForms.discussions.CommentForm(request.POST)

        if form.is_valid():
            new = MDR.DiscussionComment(
                post=post,
                body=form.cleaned_data['body'],
                author=request.user,
            )
            new.save()
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[new.post.pk]) + "#comment_%s" % new.id)
        else:
            return render(request, "aristotle_mdr/discussions/new.html", {"form": form})

    def get(self, request, *args, **kwargs):
        # It makes no sense to "GET" this page, so push them back to the discussion
        post = self.get_object()
        return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))


class DeletePost(LoginRequiredMixin, ConfirmDeleteView):
    """ A confirm delete view to delete a post and all associated comments """
    confirm_template = "aristotle_mdr/generic/actions/confirm_delete.html"

    form_delete_button_text = _("Delete")
    warning_text = _("You are about to delete a discussion post \
                     and all associated comments. Confirm below, or click cancel to return to the item.")
    form_title = "Delete Discussion Post"
    model_base = MDR.DiscussionPost

    permission_checks = [perms.can_delete_discussion_post]

    raise_exception = True
    redirect_unauthenticated_users = True

    reverse_url = 'aristotle:discussionsPost'
    # Override lookup pk
    item_kwarg = "pid"

    def perform_deletion(self):
        post = self.item

        post.comments.all().delete()
        post.delete()

    def get_success_url(self):
        post = self.item
        workgroup = post.workgroup

        return reverse("aristotle:discussionsWorkgroup", args=[workgroup.pk])


class EditPost(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, PostMixin, UpdateView):
    model = MDR.DiscussionPost
    fields = ['workgorup', 'title', 'relatedItems']
    permission_required = "aristotle_mdr.user_can_alter_post"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get(self, request, *args, **kwargs):
        post = self.get_object()
        form = MDRForms.discussions.EditPostForm(instance=post)

        return render(request, "aristotle_mdr/discussions/edit.html", {"form": form, 'post': post})

    def post(self, request, *args, **kwargs):
        post = self.get_object()
        form = MDRForms.discussions.EditPostForm(request.POST)  # A form bound to the POST data

        if not perms.user_can_alter_post(request.user, post):
            raise PermissionDenied

        if form.is_valid():
            # process the data in form.cleaned_data as required
            post.title = form.cleaned_data['title']
            post.body = form.cleaned_data['body']
            post.save()
            post.relatedItems.set(form.cleaned_data['relatedItems'])

            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))


class CommentMixin(object):
    def get_object(self, queryset=None):
        comment = get_object_or_404(MDR.DiscussionComment, pk=self.kwargs['cid'])
        post = comment.post

        if not comment or not post:
            raise Http404

        return comment


class DeleteComment(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, CommentMixin, DeleteView):
    model = MDR.DiscussionComment
    permission_required = "aristotle_mdr.can_delete_comment"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get_success_url(self):
        # TODO: How does this work, is it even tested?
        from django.utils.functional import lazy
        success_url = lazy(reverse, self)('aristotle:discussionsPost', args=self.kwargs['cid'])
        return success_url

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        comment = self.get_object()
        post = comment.post

        comment.delete()

        return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))


class EditComment(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, CommentMixin, UpdateView):
    model = MDR.DiscussionComment
    fields = ['body']
    permission_required = "aristotle_mdr.user_can_alter_comment"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get(self, request, *args, **kwargs):
        comment = self.get_object()
        post = comment.post
        form = MDRForms.discussions.CommentForm(instance=comment)

        return render(request, "aristotle_mdr/discussions/edit_comment.html", {'post': post, 'comment_form': form})

    def post(self, request, *args, **kwargs):
        comment = self.get_object()

        form = MDRForms.discussions.CommentForm(request.POST)
        if form.is_valid():
            comment.body = form.cleaned_data['body']
            comment.save()

            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[comment.post.pk]) + "#comment_%s" % comment.id)
