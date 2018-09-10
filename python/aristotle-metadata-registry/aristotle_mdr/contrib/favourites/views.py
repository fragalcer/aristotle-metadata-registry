from django.shortcuts import get_object_or_404
from aristotle_mdr.utils import url_slugify_concept
from django.contrib.auth.decorators import login_required
from aristotle_mdr.models import _concept
from aristotle_mdr.perms import user_can_view
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http.response import JsonResponse, HttpResponseRedirect
from aristotle_mdr.contrib.favourites.models import Favourite, Tag
from django.db.models import Sum, Case, When, Count, Max, Min, F

import json
from collections import defaultdict


class ToggleFavourite(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        itemid = self.kwargs['iid']
        item = get_object_or_404(_concept, pk=itemid).item

        if not user_can_view(request.user, item):
            raise PermissionDenied

        favourited = request.user.profile.toggleFavourite(item)

        if request.is_ajax():
            return self.get_json_response(item, favourited)
        else:
            if self.request.GET.get('next', None):
                return HttpResponseRedirect(self.request.GET.get('next'))
            else:
                return self.redirect_with_message(item, favourited)

    def get_message(self, item, favourited):

        if favourited:
            message = _("%s added to favourites.") % (item.name)
        else:
            message = _("%s removed from favourites.") % (item.name)

        message = _(message + " Review your favourites from the user menu.")
        return message

    def redirect_with_message(self, item, favourited):
        message = self.get_message(item, favourited)
        messages.add_message(self.request, messages.SUCCESS, message)
        return HttpResponseRedirect(url_slugify_concept(item))

    def get_json_response(self, item, favourited):
        message = self.get_message(item, favourited)
        response_dict = {
            'success': True,
            'message': message,
            'favourited': favourited
        }
        return JsonResponse(response_dict)


class EditTags(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):

        user = self.request.user
        post_data = self.request.POST
        item_id = self.kwargs['iid']
        item = get_object_or_404(_concept, pk=item_id)

        # Get all the tags on this item by this user
        current_tags = Favourite.objects.filter(
            tag__profile=user.profile,
            tag__primary=False,
            item=item
        ).values_list('tag__name', flat=True)

        tags_json = post_data.get('tags', '')

        if tags_json:
            tags = set(json.loads(tags_json))
            current_set = set(current_tags)

            new = tags - current_set
            deleted = current_set - tags

            for tag in new:
                tag_obj, created = Tag.objects.get_or_create(
                    profile=user.profile,
                    name=tag,
                    primary=False
                )
                Favourite.objects.create(
                    tag=tag_obj,
                    item=item
                )

            for tag in deleted:
                tag_obj, created = Tag.objects.get_or_create(
                    profile=user.profile,
                    name=tag,
                    primary=False
                )
                Favourite.objects.filter(
                    tag=tag_obj,
                    item=item
                ).delete()

        return self.get_json_response()

    def get_json_response(self, success=True):
        response_dict = {
            success: success,
        }

        if success:
            response_dict['message'] = 'Tags Updated'

        return JsonResponse(response_dict)


class FavouritesAndTags(LoginRequiredMixin, ListView):

    paginate_by = 20
    template_name = "aristotle_mdr/favourites/userFavourites.html"

    def get_queryset(self):

        favs = Favourite.objects.filter(
            tag__profile=self.request.user.profile
        ).select_related('tag', 'item')

        items = {}

        for fav in favs:
            if fav.item_id not in items:
                items[fav.item_id] = {
                    'item': {
                        'id': fav.item.id,
                        'name': fav.item.name,
                    },
                    'tags': [],
                    'item_favourite': 0
                }

            if fav.tag.primary:
                items[fav.item_id]['item_favourite'] = 1
            else:
                items[fav.item_id]['tags'].append({
                    'id': fav.tag.id,
                    'name': fav.tag.name
                })

        return list(items.values())

    def get_tags(self):

        # Get a users tags ordered by last usage, limited to 5
        return Tag.objects.filter(
            profile=self.request.user.profile,
            primary=False
        ).annotate(
            used=Max('favourites__created')
        ).order_by(
            F('used').desc(nulls_last=True)
        )[:5]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['help'] = self.request.GET.get('help', False)
        context['favourite'] = self.request.GET.get('favourite', False)
        context['tags'] = self.get_tags()
        return context


class TagView(LoginRequiredMixin, ListView):

    paginate_by = 20
    template_name = "aristotle_mdr/favourites/tags.html"

    def get_queryset(self):

        tagid = self.kwargs['tagid']
        return Favourite.objects.filter(
            tag_id=tagid
        ).annotate(
            item_favourite=Count(
                Case(
                    When(item__favourites__tag__primary=True, then=1)
                )
            )
        )

    def get_tag(self):

        tagid = self.kwargs['tagid']
        return Tag.objects.get(id=tagid)

    def get_context_data(self):

        context = super().get_context_data()
        tag = self.get_tag()
        context['tag'] = tag
        context['title'] = tag.name
        context['vue'] = True
        return context


class FavouriteView(LoginRequiredMixin, ListView):

    paginate_by = 20
    template_name = "aristotle_mdr/favourites/tags.html"

    def get_queryset(self):

        try:
            tag = Tag.objects.get(profile=self.request.user.profile, primary=True)
        except Tag.DoesNotExist:
            return Favourite.objects.none()

        return Favourite.objects.filter(tag=tag)

    def get_context_data(self):

        context = super().get_context_data()
        context['title'] = 'My Favourites'
        return context


class AllTagView(LoginRequiredMixin, ListView):

    paginate_by = 20
    template_name = "aristotle_mdr/favourites/all_tags.html"

    def get_queryset(self):
        return Tag.objects.filter(
            profile=self.request.user.profile,
            primary=False
        ).annotate(num_items=Count('favourites'))
