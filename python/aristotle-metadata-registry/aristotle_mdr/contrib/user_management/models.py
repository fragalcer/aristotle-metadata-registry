from aristotle_mdr.fields import LowerEmailField
from improved_user.model_mixins import AbstractUser

from django.db import models
from django.utils.translation import ugettext_lazy as _


class User(AbstractUser):
    email = LowerEmailField(_('email address'), max_length=254, unique=True)

    @property
    def display_name(self):
        if self.short_name:
            return self.short_name
        if self.full_name:
            return self.short_name

        return self.censored_email

    @property
    def censored_email(self):
        return "{start}...{end}".format(
            start=self.email[:self.email.index('@')+2],
            end=self.email[self.email.rindex('.')-1:]
        )
