from django.db import models
from aristotle_mdr.models import RegistrationAuthority


class ValidationRules(models.Model):
    class Meta:
        abstract = True

    rules = models.TextField(
        default=''
    )


class RAValidationRules(ValidationRules):
    registration_authority = models.ForeignKey(
        RegistrationAuthority,
        unique=True,
        on_delete=models.CASCADE
    )

    def can_view(self, user):
        return (user in self.registration_authority.managers.all())

    def can_edit(self, user):
        return (user in self.registration_authority.managers.all())


class RegistryValidationRules(ValidationRules):

    def can_view(self, user):
        return user.is_superuser

    def can_edit(self, user):
        return user.is_superuser
