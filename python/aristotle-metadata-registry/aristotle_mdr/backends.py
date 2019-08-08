from django.contrib.auth.backends import ModelBackend
from aristotle_mdr import perms
from aristotle_mdr.utils import fetch_aristotle_settings


class AristotleBackend(ModelBackend):

    def has_module_perms(self, user_obj, app_label):
        """
        Returns True if the requested app is an aristotle extension.
        Actual permissions to edit/change content are covered in aristotle_mdr.admin
        Otherwise, it returns as per Django permissions
        """
        extensions = fetch_aristotle_settings().get('CONTENT_EXTENSIONS', [])
        if app_label in extensions + ["aristotle_mdr"]:
            return perms.user_is_authenticated_and_active(user_obj)
        return super().has_module_perms(user_obj, app_label)

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True

        app_label, perm_name = perm.split('.', 1)
        extensions = fetch_aristotle_settings().get('CONTENT_EXTENSIONS', [])

        if app_label == "aristotle_mdr" and hasattr(perms, perm_name):
            if obj:
                return getattr(perms, perm_name)(user_obj, obj)
            else:
                return getattr(perms, perm_name)(user_obj)

        from django.apps import apps
        from aristotle_mdr.models import _concept

        perm_parts = perm_name.split("_")
        if len(perm_parts) == 2:
            model = apps.get_model(app_label, perm_parts[1])
        elif obj is not None:
            model = type(obj)
        else:
            model = int

        if app_label in extensions + ["aristotle_mdr"] and issubclass(model, _concept):
            # This is required so that a user can correctly delete the 'concept' parent class in the admin site.

            # This is a rough catch all, and is designed to indicate a user could
            # delete an item type, but not a specific item.
            if (
                perm_name.startswith('delete_') or
                perm_name.startswith('create_') or
                perm_name.startswith('add_')
            ):
                if obj is None:
                    return perms.user_is_authenticated_and_active(user_obj)
                else:
                    return perms.user_can_edit(user_obj, obj)

        if app_label in extensions + ["aristotle_mdr"]:
            if perm_name == "delete_concept_from_admin":
                return obj is None or perms.user_can_edit(user_obj, obj)

        if perm == "aristotle_mdr.can_create_metadata":
            return perms.user_is_authenticated_and_active(user_obj)

        if perm == "aristotle_mdr.view_workgroup":
            return perms.user_can_view_workgroup(user_obj, obj)
        if perm == "aristotle_mdr.can_leave_workgroup":
            return perms.user_in_workgroup(user_obj, obj)
        if perm == "aristotle_mdr.change_workgroup_memberships":
            return perms.user_is_workgroup_manager(user_obj, obj)
        if perm == "aristotle_mdr.change_workgroup":
            return perms.user_is_workgroup_manager(user_obj, obj)
        if perm == "aristotle_mdr.can_archive_workgroup":
            return perms.user_is_workgroup_manager(user_obj, obj)

        if perm == "aristotle_mdr.can_view_discussions_in_workgroup":
            return perms.user_in_workgroup(user_obj, obj)
        if perm == "aristotle_mdr.can_post_discussion_in_workgroup":
            return perms.user_in_workgroup(user_obj, obj)
        if perm == "aristotle_mdr.can_view_discussion_post":
            return perms.user_in_workgroup(user_obj, obj.workgroup)

        if perm == "aristotle_mdr.view_registrationauthority_details":
            return (
                perms.user_is_registation_authority_manager(user_obj, obj) or
                perms.user_is_registrar(user_obj, obj)
            )
        if perm == "aristotle_mdr.change_registrationauthority":
            return perms.user_is_registation_authority_manager(user_obj, obj)
        if perm == "aristotle_mdr.change_registrationauthority_memberships":
            return perms.user_is_registation_authority_manager(user_obj, obj)

        if perm == "user_can_create_workgroup":
            return perms.user_can_create_workgroup(user_obj)

        from aristotle_mdr.contrib.links import perms as link_perms
        if perm == "aristotle_mdr_links.add_link":
            return link_perms.user_can_make_link(user_obj)

        return super().has_perm(user_obj, perm, obj)
