from django.db import models
from django.utils.translation import ugettext_lazy as _
from improved_user.model_mixins import AbstractUser

from aristotle_mdr.fields import LowerEmailField


class User(AbstractUser):
    email = LowerEmailField(_('email address'), max_length=254, unique=True)
    perm_view_all_metadata = models.BooleanField(
        default=False,
        verbose_name="Allow user to view all metadata",
        help_text="Enable this to allow a user to see all metadata stored in the registry"
    )

    @property
    def first_name(self):
        return self.short_name

    @property
    def last_name(self):
        return self.full_name

    @property
    def display_name(self):
        if self.short_name:
            return self.short_name
        if self.full_name:
            return self.full_name

        return self.censored_email

    @property
    def censored_email(self):
        return "{start}...{end}".format(
            start=self.email[:self.email.index('@') + 2],
            end=self.email[self.email.rindex('.') - 1:]
        )

    class ReportBuilder:
        exclude = ('password',)
