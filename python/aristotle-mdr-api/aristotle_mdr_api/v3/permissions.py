from rest_framework.permissions import IsAuthenticated, BasePermission, SAFE_METHODS
from aristotle_mdr_api.token_auth.permissions import TokenOrReadOnlyPerm


class IsSuperuserOrReadOnly(BasePermission):
    """
    Allows access only to super users.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            request.user and
            request.userself.is_authenticated and
            request.user.is_superuser
        )


AuthAndTokenOrRO = (IsAuthenticated & TokenOrReadOnlyPerm)  # type: ignore
