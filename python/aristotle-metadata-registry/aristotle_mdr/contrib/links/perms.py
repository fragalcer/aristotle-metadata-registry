from aristotle_mdr import perms


def user_can_change_link(user, link):
    """
    If a user can edit any concept in a link, they can edit the link.
    """
    if user.is_superuser:
        return True

    if link.concepts().editable(user).exists():
        # If a user can edit at least one concept, lets let them edit this link
        return True

    return False


def user_can_make_link(user):
    """
    If a user can create metadata, they can make links
    """
    return perms.user_is_authenticated_and_active(user)
