from rest_framework import permissions
from aristotle_mdr_api.token_auth.permissions import (
    TokenOrReadOnlyPerm,
    IsAuthenticated
)


class IsSuperuserOrReadOnly(permissions.BasePermission):
    """
    Allows access only to super users.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user and
            request.userself.is_authenticated and
            request.user.is_superuser
        )


AuthAndTokenOrRO = (IsAuthenticated & TokenOrReadOnlyPerm)  # type: ignore
