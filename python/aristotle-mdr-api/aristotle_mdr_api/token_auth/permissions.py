from rest_framework.permissions import BasePermission, SAFE_METHODS


class BaseTokenPermissions(BasePermission):
    """
    Base Token permission
    """

    permission_key = 'default'
    non_token_read = False
    non_token_write = False

    def has_permission(self, request, view):
        token = request.auth

        # request.auth will be None when using any other default authentication class
        if token is not None:
            if hasattr(view, 'permission_key'):
                permission_key = getattr(view, 'permission_key')
            else:
                permission_key = self.permission_key

            hasread = False
            haswrite = False

            perms = token.permissions

            if permission_key in perms.keys():
                perm = perms[permission_key]

                if 'read' in perm:
                    hasread = perm['read']

                if 'write' in perm:
                    haswrite = perm['write']
        else:
            # Default for non token auths
            hasread = self.non_token_read
            haswrite = self.non_token_write

        if request.method in SAFE_METHODS and hasread:
            return True

        if request.method not in SAFE_METHODS and haswrite:
            return True

        return False


class IsSuperuser(BasePermission):
    """
    Allows access to only to superusers.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class TokenOrReadOnlyPerm(BaseTokenPermissions):
    """
    Permission that allows token's
    But only read non token requests are allowed
    """
    non_token_read = True
    non_token_write = False


class TokenOrAllowedPerm(BaseTokenPermissions):
    """
    Permission that allows token's
    and does not restrict non token requests
    (Should be used in combination with other permissions)
    """
    non_token_read = True
    non_token_write = True
