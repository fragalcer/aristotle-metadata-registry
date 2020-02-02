from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response

from aristotle_mdr_api.v4.permissions import AuthCanViewEdit, UnAuthenticatedUserCanView
from aristotle_mdr_api.v4.concepts import serializers
from aristotle_mdr.models import _concept, concept, aristotleComponent, SupersedeRelationship
from aristotle_mdr.views.versions import VersionsMixin
from aristotle_mdr.contrib.publishing.models import VersionPermissions
from aristotle_mdr.perms import user_can_edit
from aristotle_mdr.contrib.links.utils import get_links_for_concept
from aristotle_mdr.utils.utils import is_active_extension

from django.db.models import Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

import collections
from re import finditer
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
    permission_classes = (UnAuthenticatedUserCanView,)
    permission_key = 'metadata'
    max_graph_depth = 50

    def get(self, request, pk, format=None):
        item = self.get_object()

        seen_items_ids = set()
        queue = collections.deque([item])
        nodes = []
        edges = []

        # BFS across superseding relations
        while queue and len(queue) < self.max_graph_depth:
            # Don't go too deep because that will be very slow
            current_item = queue.popleft()
            if current_item.id not in seen_items_ids:
                if perms.user_can_view(self.request.user, current_item):
                    serialised_item = ConceptSerializer(current_item).data
                    serialised_item["node_options"] = {"shape": "ellipse", "borderWidth": 2, "margin": 3,
                                                       "font": {"size": 15}}
                    nodes.append(serialised_item)

            # Iterate across the newer items
            for superseded_by_relation in current_item.superseded_by_items_relation_set.filter(proposed=False).all():
                newer = superseded_by_relation.newer_item
                if newer.id not in seen_items_ids:
                    if perms.user_can_view(self.request.user, newer):
                        nodes.append(ConceptSerializer(newer).data)
                        queue.append(newer)
                        seen_items_ids.add(newer.id)

            # Iterate across the older items
            for sup_rel in current_item.superseded_items_relation_set.filter(proposed=False).all():
                older = sup_rel.older_item
                if older.id not in seen_items_ids:
                    if perms.user_can_view(self.request.user, older):
                        nodes.append(ConceptSerializer(sup_rel.older_item).data)
                        queue.append(sup_rel.older_item)
                        seen_items_ids.add(sup_rel.older_item.id)

            seen_items_ids.add(current_item.id)

        edge_query = Q(older_item_id__in=seen_items_ids) | Q(newer_item_id__in=seen_items_ids)
        supersede_relationships_queryset = SupersedeRelationship.objects.filter(edge_query)

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
        relational_attr = self.get_object()

        seen_items_ids = set()
        # queue = collections.deque([relational_attr])
        nodes = []
        edges = []

        source_item = ConceptSerializer(relational_attr).data
        source_item["type"] = self.split_camel_case(relational_attr.__class__.__name__)
        source_item["node_options"] = {
            "shape": "ellipse",
            "borderWidth": 2, "margin": 3,
            "font": {"size": 15}
        }
        nodes.append(source_item)

        if hasattr(relational_attr, 'relational_attributes'):

            for queryset in relational_attr.relational_attributes.values():
                for related_concept in queryset['qs']:
                    related_item = related_concept.item
                    if perms.user_can_view(self.request.user, related_item):
                        serialized_item = ConceptSerializer(related_item).data
                        serialized_item["type"] = self.split_camel_case(related_item.__class__.__name__)
                        if serialized_item["id"] not in seen_items_ids and len(nodes) < settings.MAXIMUM_NUMBER_OF_NODES_IN_GRAPHS:
                            nodes.append(serialized_item)

                            if is_active_extension("comet"):
                                from comet.models import Indicator, IndicatorSet
                                # Change the direction of arrows from Indicator to Indicator Set:
                                if isinstance(relational_attr, IndicatorSet) and isinstance(relational_attr, Indicator):
                                    edges.append(({"from": relational_attr.id, "to": serialized_item["id"]}))
                                else:
                                    edges.append(({"from": serialized_item["id"], "to": relational_attr.id}))
                            else:
                                edges.append(({"from": serialized_item["id"], "to": relational_attr.id}))

                            seen_items_ids.add(serialized_item["id"])

        for field in relational_attr._meta.get_fields():
            if field.is_relation and field.many_to_one and issubclass(field.related_model, concept):
                related_concept_instance = getattr(relational_attr, field.name)
                if related_concept_instance is not None:
                    related_concept_instance = related_concept_instance.item
                    if perms.user_can_view(self.request.user, related_concept_instance):
                        serialised_concept = ConceptSerializer(related_concept_instance).data
                        serialised_concept["type"] = self.split_camel_case(str(type(related_concept_instance)))
                        if serialised_concept["id"] not in seen_items_ids and len(nodes) < settings.MAXIMUM_NUMBER_OF_NODES_IN_GRAPHS:
                            nodes.append(serialised_concept)
                            edges.append({"from": relational_attr.id, "to": serialised_concept["id"]})
                            seen_items_ids.add(serialised_concept["id"])

            if field.is_relation and field.one_to_many and issubclass(field.related_model, aristotleComponent):
                for aris_comp_field in field.related_model._meta.get_fields():
                    if aris_comp_field.is_relation and aris_comp_field.many_to_one and\
                            issubclass(aris_comp_field.related_model, concept) and aris_comp_field.related_model != type(relational_attr):
                        queryset = getattr(relational_attr, field.get_accessor_name()).all()
                        for component in queryset:
                            component_instance = getattr(component, aris_comp_field.name)
                            if component_instance is not None:
                                serialised_concept_instance = ConceptSerializer(component_instance).data
                                serialised_concept_instance["type"] = self.split_camel_case(component_instance.__class__.__name__)
                                if serialised_concept_instance["id"] not in seen_items_ids and len(nodes) < settings.MAXIMUM_NUMBER_OF_NODES_IN_GRAPHS:
                                    nodes.append(serialised_concept_instance)
                                    edges.append({"from": serialised_concept_instance["id"], "to": relational_attr.id})
                                    seen_items_ids.add(serialised_concept_instance["id"])

        json_response = {'nodes': nodes, 'edges': edges}

        return Response(
            json_response,
            status=status.HTTP_200_OK
        )

    @staticmethod
    def split_camel_case(identifier):
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


class ListVersionsView(ObjectAPIView, VersionsMixin):
    """ List the versions of an item  """

    def get(self, request, *args, **kwargs):
        """
        Return the list of associated versions
        """
        # Get the versions
        metadata_item = self.get_object()
        versions = self.get_versions(concept, self.request.user)
        versions = versions.order_by("-revision__date_created")

        # Serialize the versions
        serializer = serializers.VersionSerializer(versions, many=True)

        return Response(
            {'versions': serializer.data},
            status.HTTP_200_OK)


class ListVersionsPermissionsView(ObjectAPIView, VersionsMixin):
    """List the version permissions of an item."""

    def get(self, request, *args, **kwargs):
        metadata_item = self.get_object()
        versions = self.get_concept_versions_for_user(metadata_item, self.request.user)
        versions.order_by("-revision__date_created")

        # Lookup all the respective versions
        permissions = []
        for version in versions:
            version_permission = VersionPermissions.objects.get_object_or_none(version=version)
            permissions.append(version_permission)

        serializer = serializers.VersionPermissionsSerializer(permissions, many=True)

        return Response({'permissions': serializer.data},
                        status.HTTP_200_OK)


class UpdateVersionPermissionsView(generics.ListAPIView, VersionsMixin):
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
        versions = self.get_concept_versions_for_user(self.item, self.request.user)
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


class GetVersionsPermissionsView(ObjectAPIView, VersionsMixin):
    """ Gets the visibility permissions of a version """

    def get(self, request, *args, **kwargs):
        version_pk = kwargs.get('vpk', None)

        metadata_item = self.get_object()
        version = self.get_versions()
        version = version.filter(pk=version_pk)[0]

        # Get the versions viewing permissions
        version_permission = VersionPermissions.objects.get_object_or_none(version=version)

        return Response(version_permission.visibility, status.HTTP_200_OK)
