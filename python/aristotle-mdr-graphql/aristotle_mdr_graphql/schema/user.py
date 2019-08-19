import graphene
from graphene_django.types import DjangoObjectType
from django.contrib.auth import get_user_model


User = get_user_model()


# class ProfileType(DjangoObjectType):
#     class Meta:
#         model = PossumProfile
#         exclude_fields = [
#             'savedActiveWorkgroup',
#             'profilePictureWidth',
#             'profilePictureHeight',
#             'profilePicture',
#             'user',
#         ]


class UserType(DjangoObjectType):
    class Meta:
        model = User
        exclude_fields = [
            'password',
            'is_superuser',
            'is_staff',
        ]


class SingleUserQuery(graphene.ObjectType):
    """Returns the current authenticated user"""
    user = graphene.Field(UserType)

    def resolve_user(self, info, **kwargs):

        if not info.context.user.is_authenticated:
            return User.objects.none()
        else:
            return info.context.user
