from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response

from aristotle_mdr_api.v4.permissions import AuthCanViewEdit, UnAuthenticatedUserCanView
from aristotle_mdr_api.v4.concepts import serializers
from aristotle_mdr.models import _concept, concept, aristotleComponent, SupersedeRelationship
from aristotle_mdr.contrib.publishing.models import VersionPermissions
from aristotle_mdr.perms import user_can_edit
from aristotle_mdr.contrib.links.utils import get_links_for_concept

from django.db.models import Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

import collections
from re import finditer
import reversion
from typing import List

from aristotle_mdr_api.v4.concepts.serializers import (
    ConceptSerializer,
    SupersedeRelationshipSerialiser
)
from aristotle_mdr_api.v4.views import ObjectAPIView
from aristotle_mdr import perms

import logging

logger = logging.getLogger(__name__)


class ConceptView(generics.RetrieveAPIView):
    permission_classes = (UnAuthenticatedUserCanView,)

    permission_key = 'metadata'

    serializer_class = serializers.ConceptSerializer
    queryset = _concept.objects.all()


class SupersedesGraphicalConceptView(ObjectAPIView):
    """Retrieve a Graphical Representation of the Supersedes Relationships"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'

    def get(self, request, pk, format=None):
        item = self.get_object()

        seen_items_ids = set()
        queue = collections.deque([item])
        nodes = []
        edges = []
        q_objects = Q()

        while queue and len(queue) < 50:
            current_item = queue.popleft()
            if current_item.id not in seen_items_ids:
                if perms.user_can_view(self.request.user, current_item):
                    serialised_item = ConceptSerializer(current_item).data
                    serialised_item["node_options"] = {"shape": "ellipse", "borderWidth": 2, "margin": 3,
                                                       "font": {"size": 15}}
                    nodes.append(serialised_item)

            for sup_by_rel in current_item.superseded_by_items_relation_set.filter(proposed=False).all():
                newer = sup_by_rel.newer_item
                if newer.id not in seen_items_ids:
                    if perms.user_can_view(self.request.user, current_item):
                        nodes.append(ConceptSerializer(newer).data)
                        queue.append(newer)
                        seen_items_ids.add(newer.id)

            for sup_rel in current_item.superseded_items_relation_set.filter(proposed=False).all():
                if sup_rel.older_item.id not in seen_items_ids:
                    if perms.user_can_view(self.request.user, current_item):
                        nodes.append(ConceptSerializer(sup_rel.older_item).data)
                        queue.append(sup_rel.older_item)
                        seen_items_ids.add(sup_rel.older_item.id)
            seen_items_ids.add(current_item.id)

        seen_items_ids = list(seen_items_ids)

        for item in seen_items_ids:
            q_objects.add(Q(older_item__id=item), Q.OR)
            q_objects.add(Q(newer_item__id=item), Q.OR)

        supersede_relationships_queryset = SupersedeRelationship.objects.filter(q_objects)

        for item in supersede_relationships_queryset:
            edges.append(SupersedeRelationshipSerialiser(item).data)

        json_response = {'nodes': nodes, 'edges': edges}

        return Response(
            json_response,
            status=status.HTTP_200_OK
        )


class GeneralGraphicalConceptView(ObjectAPIView):
    """Retrieve a graphical representation of the general relationships"""
    permission_classes = (UnAuthenticatedUserCanView,)
    permission_key = 'metadata'

    def get(self, request, pk, format=None):
        item = self.get_object()

        seen_items_ids = set()
        # queue = collections.deque([item])
        nodes = []
        edges = []

        source_item = ConceptSerializer(item).data
        source_item["type"] = self.camel_case_split(item.__class__.__name__)
        source_item["node_options"] = {
            "shape": "ellipse",
            "borderWidth": 2, "margin": 3,
            "font": {"size": 15}
        }
        nodes.append(source_item)

        if hasattr(item, 'relational_attributes'):
            for d in item.relational_attributes.values():
                for rel_attr in d['qs']:
                    if perms.user_can_view(self.request.user, rel_attr):
                        serialised_rel_attr = ConceptSerializer(rel_attr).data
                        serialised_rel_attr["type"] = self.camel_case_split(rel_attr.__class__.__name__)
                        if serialised_rel_attr["id"] not in seen_items_ids and len(
                                nodes) < settings.MAXIMUM_NUMBER_OF_NODES_IN_GENERAL_GRAPHICAL_REPRESENTATION:
                            nodes.append(serialised_rel_attr)
                            edges.append(({"from": serialised_rel_attr["id"], "to": item.id}))
                            seen_items_ids.add(serialised_rel_attr["id"])

        for field in item._meta.get_fields():
            if field.is_relation and field.many_to_one and issubclass(field.related_model, concept):
                related_concept_instance = getattr(item, field.name)
                if related_concept_instance is not None:
                    if perms.user_can_view(self.request.user, related_concept_instance):
                        serialised_concept = ConceptSerializer(related_concept_instance).data
                        serialised_concept["type"] = self.camel_case_split(related_concept_instance.__class__.__name__)
                        if serialised_concept["id"] not in seen_items_ids and len(
                                nodes) < settings.MAXIMUM_NUMBER_OF_NODES_IN_GENERAL_GRAPHICAL_REPRESENTATION:
                            nodes.append(serialised_concept)
                            edges.append({"from": item.id, "to": serialised_concept["id"]})
                            seen_items_ids.add(serialised_concept["id"])
            if field.is_relation and field.one_to_many and issubclass(field.related_model, aristotleComponent):
                for aris_comp_field in field.related_model._meta.get_fields():
                    if aris_comp_field.is_relation and aris_comp_field.many_to_one and \
                            issubclass(aris_comp_field.related_model,
                                       concept) and aris_comp_field.related_model != type(item):
                        queryset = getattr(item, field.get_accessor_name()).all()
                        for component in queryset:
                            component_instance = getattr(component, aris_comp_field.name)
                            if component_instance is not None:
                                serialised_concept_instance = ConceptSerializer(component_instance).data
                                serialised_concept_instance["type"] = self.camel_case_split(
                                    component_instance.__class__.__name__)
                                if serialised_concept_instance["id"] not in seen_items_ids and len(
                                        nodes) < settings.MAXIMUM_NUMBER_OF_NODES_IN_GENERAL_GRAPHICAL_REPRESENTATION:
                                    nodes.append(serialised_concept_instance)
                                    edges.append({"from": serialised_concept_instance["id"], "to": item.id})
                                    seen_items_ids.add(serialised_concept_instance["id"])

        json_response = {'nodes': nodes, 'edges': edges}

        return Response(
            json_response,
            status=status.HTTP_200_OK
        )

    @staticmethod
    def camel_case_split(identifier):
        matches = finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
        return ' '.join([m.group(0) for m in matches])


class ConceptLinksView(ObjectAPIView):
    """Retrieve a graphical representation of the links relations"""
    permission_classes = (UnAuthenticatedUserCanView,)

    def get(self, request, *args, **kwargs):
        concept = self.get_object()
        links = get_links_for_concept(concept)

        seen_concepts = set()
        nodes = []
        edges = []
        for link in links:
            # Id to use in output for link (so it doesnt clash with concept ids)
            link_id = 'link_{id}'.format(id=link.id)
            # Add link node
            nodes.append({
                'id': link_id,
                'name': link.relation.name,
                'definition': link.relation.definition,
                'short_definition': link.relation.short_definition,
            })
            for end in link.linkend_set.all():
                # Add concept node
                if end.concept_id not in seen_concepts:
                    nodes.append(ConceptSerializer(end.concept).data)
                    seen_concepts.add(end.concept_id)
                # Add edge
                edges.append({
                    'from': link_id,
                    'to': end.concept_id
                })

        return Response(
            {'nodes': nodes, 'edges': edges},
            status.HTTP_200_OK
        )


class ListVersionsView(ObjectAPIView):
    """ List the versions of an item  """

    def get(self, request, *args, **kwargs):
        """
        Return the list of associated versions
        """
        # Get the versions
        metadata_item = self.get_object()
        versions = reversion.models.Version.objects.get_for_object(metadata_item)
        versions = versions.order_by("-revision__date_created")

        # Serialize the versions
        serializer = serializers.VersionSerializer(versions, many=True)

        return Response(
            {'versions': serializer.data},
            status.HTTP_200_OK)


class ListVersionsPermissionsView(ObjectAPIView):

    """List the version permissions of an item"""

    def get(self, request, *args, **kwargs):
        metadata_item = self.get_object()
        versions = reversion.models.Version.objects.get_for_object(metadata_item)
        versions.order_by("-revision__date_created")

        # Lookup all the respective versions
        permissions = []
        for version in versions:
            version_permission = VersionPermissions.objects.get_object_or_none(version=version)
            permissions.append(version_permission)

        serializer = serializers.VersionPermissionsSerializer(permissions, many=True)

        return Response({'permissions': serializer.data},
                        status.HTTP_200_OK)


class UpdateVersionPermissionsView(generics.ListAPIView):
    """Updates the visibility permissions of all versions associated with an id"""
    version_ids: List = []

    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.VersionPermissionsSerializer
    lookup_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        pk = self.kwargs[self.lookup_url_kwarg]
        # Get item
        self.item = get_object_or_404(_concept, pk=pk).item
        if not user_can_edit(self.request.user, self.item):
            raise PermissionDenied()
        # Get associated versions
        versions = reversion.models.Version.objects.filter(object_id=self.item.id)

        self.version_ids = [version.pk for version in versions]

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Get the matching version permissions
        version_permissions = VersionPermissions.objects.filter(pk__in=self.version_ids)

        return version_permissions

    def get_serializer_context(self):
        context = super().get_serializer_context()

        # Have to add this for when swagger docs are made
        if hasattr(self, 'version_ids'):
            context.update({'version_ids': self.version_ids})

        return context

    def update(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer(
            queryset, data=request.data, many=True,
            context={'version_ids': self.version_ids}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class GetVersionsPermissionsView(ObjectAPIView):
    """ Gets the visibility permissions of a version """

    def get(self, request, *args, **kwargs):
        version_pk = kwargs.get('vpk', None)

        metadata_item = self.get_object()
        version = reversion.models.Version.objects.get_for_object(metadata_item)
        version = version.filter(pk=version_pk).first()

        # Get the versions viewing permissions
        version_permission = VersionPermissions.objects.get_object_or_none(version=version)

        return Response(version_permission.visibility, status.HTTP_200_OK)
