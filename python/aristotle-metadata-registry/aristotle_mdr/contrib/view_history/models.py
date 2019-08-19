from django.conf import settings
from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr import models as MDR
from aristotle_mdr.fields import ConceptForeignKey


class UserViewHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="recently_viewed_metadata", on_delete=models.PROTECT)
    concept = ConceptForeignKey(MDR._concept, related_name='user_view_history', on_delete=models.CASCADE)
    view_date = models.DateTimeField(
        default=now,
        help_text=_("When the item was viewed")
    )
