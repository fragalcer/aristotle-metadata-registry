from django.db import models
from mptt.managers import TreeManager
from mptt.querysets import TreeQuerySet


class FrameworkDimensionQuerySet(TreeQuerySet):

    def visible(self, user):
        """
        Only dimensions where the parent framework is visible are visible
        This is currently only used in graphql
        """
        from comet.models import Framework

        if user.is_superuser:
            return self

        visible_frameworks = Framework.objects.all().visible(user)
        return self.filter(framework__in=visible_frameworks)


class FrameworkDimensionManager(TreeManager):

    def get_queryset(self):
        return FrameworkDimensionQuerySet(self.model, using=self._db)
