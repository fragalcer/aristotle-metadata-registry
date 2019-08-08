from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from aristotle_mdr.utils import fetch_aristotle_settings
from aristotle_mdr.contrib.reviews.const import REVIEW_STATES

import logging
logger = logging.getLogger(__name__)

VIEW_CACHE_SECONDS = 60
EDIT_CACHE_SECONDS = 60


def user_can_alter_comment(user, comment):
    return user.is_superuser or user == comment.author or user_is_workgroup_manager(user, comment.post.workgroup)


def user_can_alter_post(user, post):
    return user.is_superuser or user == post.author or user_is_workgroup_manager(user, post.workgroup)


def can_post_discussion(user):
    return user.is_active and user.profile.myWorkgroups.count() > 0


def can_comment_on_post(user, post):
    return user_in_workgroup(user, post.workgroup)


def can_delete_comment(user, comment):
    return user_can_alter_comment(user, comment)


def can_delete_discussion_post(user, post):
    return user_can_alter_post(user, post)


def user_can_publish_object(user, obj):
    if user.is_superuser:
        return True

    if user.is_anonymous:
        return False

    stewardship_organisation = obj.stewardship_organisation
    if not stewardship_organisation:
        # Can't publish "un-owned" objects
        return False
    if not getattr(obj, 'publication_details', None):
        # There is no reverse relation, don't allow publication
        return False

    return stewardship_organisation.user_has_permission(user, "publish_objects")


def can_delete_metadata(user, item):
    if item.submitter == user and item.workgroup is None:
        if not item.statuses.exists():
            return True
    return False


def user_can(user, item, method_name):
    """When custom methods are required"""
    if user.is_superuser:
        return True

    if user.is_anonymous:
        return False

    method = getattr(item, method_name)
    if callable(method):
        return method(user)

    return False


def user_can_view(user, item):
    """Can the user view the item?"""
    if user.is_superuser:
        return True
    if item.__class__ == get_user_model():  # -- Sometimes duck-typing fails --
        return user == item                 # A user can edit their own details

    if user.is_anonymous():
        user_key = "anonymous"
    else:
        user_key = str(user.id)

    can_use_cache = False
    # If the item was not modified recently, use cache
    if hasattr(item, "was_modified_very_recently") and not item.was_modified_very_recently():
        can_use_cache = True

    key = 'user_can_view_%s|%s:%s|%s' % (user_key, item._meta.app_label, item._meta.app_label, str(item.id))
    cached_can_view = cache.get(key)
    if can_use_cache and cached_can_view is not None:
        return cached_can_view

    _can_view = False

    _can_view = item.can_view(user)
    cache.set(key, _can_view, VIEW_CACHE_SECONDS)
    return _can_view


def user_can_edit(user, item):
    """Can the user edit the item?"""
    # Superusers can edit everything
    if user.is_superuser:
        return True
    # Anonymous users can edit nothing
    if user.is_anonymous():
        return False
    # A user can edit their own details
    if item.__class__ == get_user_model():  # -- Sometimes duck-typing fails --
        return user == item

    can_use_cache = False
    # If the item was not modified recently, use cache
    if hasattr(item, "was_modified_very_recently") and not item.was_modified_very_recently():
        can_use_cache = True

    user_key = str(user.id)
    key = 'user_can_edit_%s|%s:%s|%s' % (user_key, item._meta.app_label, item._meta.app_label, str(item.id))
    cached_can_edit = cache.get(key)
    if can_use_cache and cached_can_edit is not None:
        return cached_can_edit

    _can_edit = False

    if not user_can_view(user, item):
        _can_edit = False
    else:
        _can_edit = item.can_edit(user)
    cache.set(key, _can_edit, VIEW_CACHE_SECONDS)

    return _can_edit


def user_is_authenticated_and_active(user):
    return user.is_authenticated() and user.is_active


def user_can_submit_to_workgroup(user, workgroup):
    return workgroup.has_role(["submitter", "steward"], user)


def user_is_registrar(user, ra=None):
    if user.is_anonymous():
        return False
    if user.is_superuser:
        return True
    elif ra is None:
        return user.registrar_in.count() > 0
    else:
        return user in ra.registrars.all()


def user_is_registation_authority_manager(user, ra=None):
    if user.is_anonymous():
        return False
    if user.is_superuser:
        return True
    elif ra is None:
        return user.organization_manager_in.count() > 0
    else:
        return user in ra.managers.all()


def user_can_add_status(user, item):
    """Can the user add a status to this item in some RA"""
    if user.is_anonymous():
        return False
    if user.is_superuser:
        return True

    # If this item has any requested reviews for a registration authority this user is a registrar of:
    if item.rr_review_requests.visible(user):
        return True

    # Get proposed supersedes in ra's where the user is a registrar and the older item is this item
    ss_items = item.superseded_by_items_relation_set.filter(
        Q(proposed=True),
        Q(registration_authority__registrars__profile__user=user)
    )
    # If these exist user can change status on the item
    if ss_items.exists():
        return True

    if user.profile.is_registrar and item.is_public():
        return True

    return False


def user_can_add_ra_status(user, ra, item):
    """Can the user add a status to this item in this RA"""
    if user.is_anonymous():
        return False
    if user.is_superuser:
        return True

    # Must be a registrar in this ra
    if user not in ra.registrars.all():
        return False

    # If this item has any requested reviews in this ra
    if item.rr_review_requests.filter(registration_authority=ra).visible(user):
        return True

    # Get proposed supersedes in this ra involving this item
    ss_items = item.superseded_by_items_relation_set.filter(
        Q(proposed=True),
        Q(registration_authority=ra)
    )
    # If these exist user can change status on the item
    if ss_items.exists():
        return True

    return False


def user_can_supersede(user, item):
    if user.is_anonymous():
        return False
    if user.is_superuser:
        return True
    if not user_can_view(user, item):
        return False

    if user.profile.is_registrar:
        return True
    return False


def user_can_view_review(user, review):
    if user.is_anonymous():
        return False
    # A user can see all their requests
    if review.requester == user:
        return True

    if user.is_superuser:
        return True

    # No-one else can see a cancelled request
    if review.status == REVIEW_STATES.revoked:
        return False

    # If a registrar is in the registration authority for the request they can see it.
    if user.registrar_in.filter(pk=review.registration_authority.pk).exists():
        return True

    # If the user is a manager in the registration authority for the request they can view it.
    if user in review.registration_authority.managers.all():
        return True

    return False


def user_can_edit_review(user, review):
    if user.is_anonymous():
        return False
    # A user can edit all their requests
    if review.requester == user:
        return True

    if user.is_superuser:
        return True

    # None else can see a cancelled request
    if review.status == REVIEW_STATES.revoked:
        return False

    # If the user is a manager in the registration authority for the request they can edit it.
    return user in review.registration_authority.managers.all()


def user_can_edit_review_comment(user, reviewcomment):
    if user.is_anonymous():
        return False
    # A user can edit all their requests
    if reviewcomment.author == user:
        return True

    if user.is_superuser:
        return True

    # None else can see a cancelled request
    if reviewcomment.review.status == REVIEW_STATES.revoked:
        return False

    # If a registrar is in the registration authority for the request they can see it.
    return user in reviewcomment.request.registration_authority.managers.all()


def user_can_view_review_comment(user, reviewcomment):
    return user_can_view_review(user, reviewcomment.review)


def user_can_revoke_review(user, review):
    if user.is_anonymous():
        return False
    # A user can see all their requests
    if review.requester == user:
        return True

    if user.is_superuser:
        return True

    return False


def user_can_close_or_reopen_review(user, review):
    if user.is_anonymous():
        return False
    # A user can see all their requests
    if review.requester == user:
        return True

    if user.is_superuser:
        return True

    # If you arent the requester or a super user, you can reopen a revoked request
    if review.status == REVIEW_STATES.revoked:
        return False

    # If a registrar is in the registration authority for the request they can see it.
    return user.registrar_in.filter(pk=review.registration_authority.pk).exists()


def user_can_approve_review(user, review):
    if user.is_anonymous():
        return False
    # Can't approve a closed request
    if review.status != REVIEW_STATES.open:
        return False

    if user.is_superuser:
        return True

    # If a registrar is in the registration authority for the request they can see it.
    return user.registrar_in.filter(pk=review.registration_authority.pk).exists()


def user_can_view_workgroup(user, wg):
    return wg.can_view(user)


def user_can_manage_workgroup(user, workgroup):
    if user.is_superuser:
        return True
    elif workgroup is None:
        return user.workgroupmembership_set.filter(role='manager').exists()

    if not workgroup.stewardship_organisation.is_active():
        return False
    if workgroup.stewardship_organisation.user_has_permission(user, "manage_workgroups"):
        return True
    else:
        return workgroup.has_role('manager', user)


def user_is_workgroup_manager(user, workgroup):
    return user_can_manage_workgroup(user, workgroup)


def user_in_workgroup(user, wg):
    if user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    return user in wg.member_list.all()


def user_can_move_any_workgroup(user):
    """Checks if a user can move an item from any of their workgroups"""
    workgroup_change_access = fetch_aristotle_settings().get('WORKGROUP_CHANGES', [])

    if user.is_anonymous:
        return False

    if user.is_superuser:
        return True
    if 'admin' in workgroup_change_access and user.is_staff:
        return True
    if 'manager' in workgroup_change_access and user.profile.is_workgroup_manager():
        return True
    if 'submitter' in workgroup_change_access and user.workgroupmembership_set.filter(role="submitter").exists():
        return True

    return False


def user_can_add_or_remove_workgroup(user, workgroup):
    workgroup_change_access = fetch_aristotle_settings().get('WORKGROUP_CHANGES', [])

    if user.is_anonymous:
        return False

    if user.is_superuser:
        return True
    if 'admin' in workgroup_change_access and user.has_perm("aristotle_mdr.is_registry_administrator"):
        return True

    if workgroup:
        if 'manager' in workgroup_change_access and workgroup.has_role('manager', user):
            return True
        if 'submitter' in workgroup_change_access and workgroup.has_role('submitter', user):
            return True

    return False


def user_can_remove_from_workgroup(user, workgroup):
    return user_can_add_or_remove_workgroup(user, workgroup)


def user_can_move_to_workgroup(user, workgroup):
    return user_can_add_or_remove_workgroup(user, workgroup)


def user_can_move_between_workgroups(user, workgroup_a, workgroup_b):
    """checks if a user can move an item from A to B"""
    return user_can_remove_from_workgroup(user, workgroup_a) and user_can_move_to_workgroup(user, workgroup_b)


def user_can_query_user_list(user):
    if user.is_anonymous():
        return False
    user_visbility = fetch_aristotle_settings().get('USER_VISIBILITY', 'owner')
    return (
        user.has_perm("aristotle_mdr.is_registry_administrator") or
        user.profile.is_stewardship_organisation_admin() or
        ('workgroup_manager' in user_visbility and user.profile.is_workgroup_manager()) or
        ('registation_authority_manager' in user_visbility and user.profile.is_registrar)
    )


def edit_other_users_account(viewing_user, viewed_user):
    return view_other_users_account(viewing_user, viewed_user)


def view_other_users_account(viewing_user, viewed_user):
    from aristotle_mdr.models import StewardOrganisation
    user = viewing_user
    if user.is_anonymous:
        return False

    if user.is_superuser:
        return True

    allowed_roles = [
        StewardOrganisation.roles.admin,
    ]

    return StewardOrganisation.objects.filter(
        members__user=viewed_user
    ).filter(
        members__user=viewing_user, members__role__in=allowed_roles
    ).active().exists()


def user_can_create_workgroup(user, steward_org=None):
    return user_is_superuser_or_has_admin_role_in_steward_organisation(user, steward_org)


def user_can_create_registration_authority(user, steward_org=None):
    return user_is_superuser_or_has_admin_role_in_steward_organisation(user, steward_org)


def user_is_superuser_or_has_admin_role_in_steward_organisation(user, steward_org=None):
    from aristotle_mdr.models import StewardOrganisation
    if user.is_superuser:
        return True
    allowed_roles = [
        StewardOrganisation.roles.admin,
    ]
    kwargs = {"members__user": user, "members__role__in": allowed_roles}
    if steward_org:
        kwargs["pk"] = steward_org.pk
    return StewardOrganisation.objects.filter(**kwargs).active().exists()


def user_can_edit_issue_label(user, label):
    if user.is_superuser:
        return True

    if label.stewardship_organisation is None:
        return False

    from aristotle_mdr.models import StewardOrganisation
    return label.stewardship_organisation.has_role(
        user=user, role=StewardOrganisation.roles.admin
    )


def can_alter_any_issue_labels(user):
    if user.is_superuser:
        return True

    from aristotle_mdr.models import StewardOrganisation, StewardOrganisationMembership
    return StewardOrganisationMembership.user_has_role_for_any_group(
        user=user, role=StewardOrganisation.roles.admin
    )
