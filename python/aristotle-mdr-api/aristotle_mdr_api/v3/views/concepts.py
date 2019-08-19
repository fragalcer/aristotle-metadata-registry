from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response

from reversion import revisions as reversion

from aristotle_mdr import models, perms
from ..serializers.base import Deserializer, Serializer
from ..filters import concept_backend
from aristotle_mdr_api.v3.permissions import AuthAndTokenOrRO

from ..views.utils import (
    DescriptionStubSerializerMixin,
    MultiSerializerViewSetMixin,
    ConceptResultsPagination,
    UUIDLookupModelMixin
)

import logging
logger = logging.getLogger(__name__)


standard_fields = ('uuid', 'concept_type','visibility_status',)
class ConceptSerializerBase(serializers.ModelSerializer):
    concept_type = serializers.SerializerMethodField()
    visibility_status = serializers.SerializerMethodField()

    class Meta:
        model = models._concept
        fields = standard_fields
    def get_concept_type(self,instance):
        item = instance.item
        out = {"app":item._meta.app_label,'model':item._meta.model_name}
        return out
    def get_visibility_status(self,instance):
        out = {"public":instance.is_public(),'locked':instance.is_locked()}
        return out

class ConceptListSerializer(DescriptionStubSerializerMixin,ConceptSerializerBase):
    class Meta:
        model = models._concept
        fields = standard_fields + ('definition', 'name')

class ConceptDetailSerializer(ConceptSerializerBase):
    fields = serializers.SerializerMethodField('get_extra_fields')
    ids = serializers.SerializerMethodField('get_identifiers')
    slots = serializers.SerializerMethodField()
    links = serializers.SerializerMethodField()
    statuses = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pyserializer = Serializer()

    def get_serialized_object(self, instance):
        return self.pyserializer.serialize([instance.item], context=self.context)[0]

    class Meta:
        model = models._concept
        fields = standard_fields+('fields','statuses','ids','slots', 'links')

    def get_extra_fields(self, instance):
        return self.get_serialized_object(instance).get('fields',[])

    def get_identifiers(self, instance):
        return self.get_serialized_object(instance).get('identifiers',[])

    def get_slots(self, instance):
        return self.get_serialized_object(instance).get('slots', [])

    def get_links(self, instance):
        return self.get_serialized_object(instance).get('links', [])

    def get_statuses(self, instance):
        return self.get_serialized_object(instance).get('statuses',[])


class ConceptViewSet(
    MultiSerializerViewSetMixin,
    mixins.CreateModelMixin,
    UUIDLookupModelMixin,
    #mixins.RetrieveModelMixin,
                    #mixins.UpdateModelMixin,

                    #viewsets.ModelViewSet):
    viewsets.ReadOnlyModelViewSet):
    """
    retrieve:
    Provides access to a specific metadata item.

    list:
    Provides access to a paginated list of metadata items.

    create:
    Create a new metadata item.
    """

    queryset = models._concept.objects.all()
    pagination_class = ConceptResultsPagination
    filter_backends = (concept_backend.ConceptFilterBackend,)
    filter_class = concept_backend.ConceptFilter

    permission_key = 'metadata'
    permission_classes = (AuthAndTokenOrRO,)

    serializers = {
        'default': ConceptDetailSerializer,
        'list': ConceptListSerializer
    }


    def get_queryset(self):
        """
        Possible arguments include:

        type (string) : restricts to a particular concept type, eg. dataelement

        """
        self.queryset = self.get_content_type_for_request().objects.all()

        queryset = super(ConceptViewSet,self).get_queryset()
        if self.request:
            locked = self.request.query_params.get('is_locked', None)
            public = self.request.query_params.get('is_public', None)
            queryset = queryset.visible(self.request.user)
        else:
            locked = None
            public = None
            queryset = queryset.public()

        if locked is not None:
            locked = locked not in ["False","0","F"]
            queryset = queryset.filter(_is_locked=locked)
        if public is not None:
            public = public not in ["False","0","F"]
            queryset = queryset.filter(_is_public=public)

        return queryset

    def get_content_type_for_request(self):
        content_type = models._concept
        concepttype = self.request.query_params.get('type', None)

        if concepttype is not None:
            ct = concepttype.lower().split(":",1)
            if len(ct) == 2:
                app,model = ct
                content_type = ContentType.objects.get(app_label=app,model=model).model_class()
            else:
                model = concepttype
                content_type = ContentType.objects.get(model=model).model_class()

            class SpecialFilter(self.filter_class):
                class Meta(self.filter_class.Meta):
                    model = content_type

            self.filter_class = SpecialFilter

        return content_type

    def check_object_permissions(self, request, obj):
        item = obj.item
        if not perms.user_can_view(request.user, item):
            raise PermissionDenied
        else:
            return obj

    def get_object(self):
        item = super(ConceptViewSet,self).get_object().item
        if not perms.user_can_view(self.request.user, item):
            raise PermissionDenied
        else:
            return item

    def create(self, request, *args, **kwargs):

        data = request.data
        if 'concept_type' in request.data.keys():
            # We've been passed a single object
            manifest = {'metadata':[data]}
        else:
            manifest = data

        try:
            created = []
            errors = []
            with transaction.atomic():
                for s in Deserializer(manifest):

                    if s.object.workgroup is None or perms.user_can_submit_to_workgroup(request.user, s.object.workgroup):
                        with reversion.create_revision():
                            created.append({
                                'uuid': s.object.uuid,
                                'url': s.object.get_absolute_url()
                            })
                            s.submitter = request.user
                            s.object.recache_states()

                            reversion.set_user(request.user)
                            reversion.set_comment(
                                _("Imported using API")
                            )
                            s.save()
                    else:
                        errors.append({
                            'message': 'You don\'t have permission to create an item in the {} Workgroup'.format(s.object.workgroup)
                        })

            return Response({'created':created,'errors':errors})
        except Exception as e:
            if settings.DEBUG and 'explode' in request.query_params.keys():
                raise
            return Response({'error': str(e)})


class SupersededRelationshipSerializer(serializers.ModelSerializer):
    older_item = serializers.SerializerMethodField()
    newer_item = serializers.SerializerMethodField()
    registration_authority = serializers.SerializerMethodField()
    class Meta:
        model = models.SupersedeRelationship
        fields = [
            'older_item', 'newer_item',
            'registration_authority',
            'message', 'date_effective',
        ]

    def get_older_item(self,instance):
        return instance.older_item.uuid

    def get_newer_item(self,instance):
        return instance.newer_item.uuid

    def get_registration_authority(self,instance):
        return instance.registration_authority.uuid


class SupersededRelationshipViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:
    Provides access to a specific metadata item.

    list:
    Provides access to a paginated list of metadata items.
    """

    queryset = models.SupersedeRelationship.approved.all()
    filter_backends = (concept_backend.SupersedeRelationshipBackend,)
    filter_class = concept_backend.SupersedeRelationshipFilter

    serializer_class = SupersededRelationshipSerializer
    permission_classes = (AuthAndTokenOrRO,)

    def get_queryset(self):
        """
        Possible arguments include:

        type (string) : restricts to a particular concept type, eg. dataelement

        """
        # from django.contrib.auth import AnonymousUser
        # self.request.user = AnonymousUser
        queryset = super().get_queryset()

        from django.db.models import Subquery

        visible_metadata = models._concept.objects.visible(self.request.user).values("pk")
        # newer_visible = MDR._concepts.visible(self.request.user)
        queryset = queryset.filter(
            newer_item__in=Subquery(visible_metadata),
            older_item__in=Subquery(visible_metadata),
        )

        return queryset
