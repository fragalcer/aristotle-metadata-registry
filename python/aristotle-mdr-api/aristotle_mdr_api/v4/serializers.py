from typing import Iterable, Dict
from django.db.models import Model
from django.db.models.query import QuerySet
from rest_framework import serializers


class MultiUpdateListSerializer(serializers.ListSerializer):
    """
    To be used for multple updates on a list serializer
    Creates new models and deletes missing models
    Needs a non required IntegerField for idA

    """
    perform_create = True # Whether to actually create the item
    perform_delete = True # Whether to delete the items
    create_if_not_in_db = False # Whether to create if not in database

    lookup_key_flag = 'id'

    def update(self, instance: QuerySet, validated_data: Iterable[Dict]):
        db_mapping: Dict[int, Model] = {obj.id: obj for obj in instance}

        existing_data = []
        new_data = []

        if self.create_if_not_in_db:
            for item in validated_data:
                if item[self.lookup_key_flag] in db_mapping:
                    existing_data.append(item)
                else:
                    new_data.append(item)
        else:
            for item in validated_data:
                if self.lookup_key_flag in item:
                    existing_data.append(item)
                else:
                    new_data.append(item)

        submitted_ids = [obj[self.lookup_key_flag] for obj in existing_data]
        return_list = []

        # Update existing item
        for item in existing_data:
            db_item = db_mapping.get(item[self.lookup_key_flag], None)
            # Make sure the id is a real item
            if db_item is not None:
                return_list.append(self.child.update(db_item, item))

        # Create new items
        if self.perform_create:
            for item in new_data:
                return_list.append(self.child.create(item))

        # Delete existing items
        if self.perform_delete:
            for iid, inst in db_mapping.items():
                if iid not in submitted_ids:
                    # Item has been removed
                    inst.delete()

        return return_list


class MultiUpdateNoDeleteListSerializer(MultiUpdateListSerializer):
    perform_delete = False


class MultiUpdateCreateIfNotInDatabase(MultiUpdateListSerializer):
    create_if_not_in_db = True
    perform_delete = False


class VersionVisibilityPermissionSerializer(MultiUpdateListSerializer):
    create_if_not_in_db = True
    perform_delete = False
    lookup_key_flag = 'version_id'