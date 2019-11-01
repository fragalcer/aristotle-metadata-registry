from rest_framework.permissions import BasePermission, SAFE_METHODS, IsAuthenticated
from aristotle_mdr import perms
from aristotle_mdr_api.token_auth.permissions import (
    IsSuperuser,
    TokenOrAllowedPerm
)


class UserCanViewEdit(BasePermission):

    # Safe methods are GET, HEAD and OPTIONS
    can_view_methods = SAFE_METHODS

    def has_object_permission(self, request, view, obj):

        if request.method in self.can_view_methods:
            return perms.user_can_view(request.user, obj)
        else:
            return perms.user_can_edit(request.user, obj)


class UserFinePerms(BasePermission):

    def has_object_permission(self, request, view, obj):

        # Safe methods are GET, HEAD and OPTIONS
        if request.method in SAFE_METHODS:
            return perms.user_can_view(request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return perms.user_can_edit(request.user, obj)
        elif request.method == 'DELETE':
            return obj.can_delete(request.user)

        return False


AuthCanViewEdit = (IsAuthenticated & TokenOrAllowedPerm & UserCanViewEdit)  # type: ignore
AuthFinePerms = (IsAuthenticated & TokenOrAllowedPerm & UserFinePerms)  # type: ignore
UnAuthenticatedUserCanView = (TokenOrAllowedPerm & UserCanViewEdit)  # type: ignore
SuperOnly = (IsSuperuser & TokenOrAllowedPerm)  # type: ignore
