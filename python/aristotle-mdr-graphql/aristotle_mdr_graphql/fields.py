from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.utils import maybe_queryset
from graphene import Field, List
from graphene_django.filter.utils import (
    get_filtering_args_from_filterset,
    get_filterset_class
)
from functools import partial
from graphene_django.utils import maybe_queryset
from graphene.types.argument import to_arguments
from collections import OrderedDict
from aristotle_mdr_graphql.filterset import (AristotleFilterSet,
                                             ConceptFilterSet)
from graphene.types.scalars import Scalar


class ObjectField(Scalar):

    @staticmethod
    def serialize(dt):
        return dt

    @staticmethod
    def parse_literal(node):
        return node.value

    @staticmethod
    def parse_value(value):
        return value


class AristotleFilterConnectionField(DjangoFilterConnectionField):

    def __init__(self, type, *args, **kwargs):
        extrameta = {
            'filterset_base_class': AristotleFilterSet
        }
        kwargs.update({'extra_filter_meta': extrameta})
        super().__init__(type, *args, **kwargs)

    @classmethod
    def connection_resolver(cls, resolver, connection, default_manager, max_limit,
                            enforce_first_or_last, filterset_class, filtering_args,
                            root, info, **args):

        filter_kwargs = {k: v for k, v in args.items() if k in filtering_args}
        qs = filterset_class(
            data=filter_kwargs,
            queryset=default_manager.get_queryset(),
            request=info.context
        ).qs

        qs = qs.visible(info.context.user)  # Top level filtering to only visible objects

        return super(DjangoFilterConnectionField, cls).connection_resolver(
            resolver,
            connection,
            qs,
            max_limit,
            enforce_first_or_last,
            root,
            info,
            **args
        )


class AristotleConceptFilterConnectionField(AristotleFilterConnectionField):
    def __init__(self, type, *args, **kwargs):

        extrameta = {
            'filterset_base_class': ConceptFilterSet,
        }

        kwargs.update({'extra_filter_meta': extrameta})
        if "description" not in kwargs.keys():
            kwargs['description'] = "Look up a collection of " + str(type._meta.model.get_verbose_name_plural())

        super(AristotleFilterConnectionField, self).__init__(type, *args, **kwargs)


class DjangoListFilterField(Field):
    """
    Custom field to use django-filter with graphene object types (without relay).
    """

    def __init__(self, _type, fields=None, extra_filter_meta=None,
                 filterset_class=None, *args, **kwargs):
        _fields = _type._meta.filter_fields
        _model = _type._meta.model
        self._model = _type._meta.model
        self.fields = fields or _fields
        meta = dict(model=_model, fields=self.fields)
        self.filterset_class = get_filterset_class(filterset_class, **meta)
        self.filtering_args = get_filtering_args_from_filterset(
            self.filterset_class, _type)
        self._base_args = None
        super().__init__(List(_type), *args, **kwargs)

    @property
    def model(self):
        return self._model

    @property
    def args(self):
        return to_arguments(self._base_args or OrderedDict(), self.filtering_args)

    @args.setter
    def args(self, args):
        self._base_args = args

    @staticmethod
    def list_resolver(resolver, default_manager, filterset_class, filtering_args, root, info, **args):
        filter_kwargs = {k: v for k, v in args.items() if k in filtering_args}
        qs = filterset_class(
            data=filter_kwargs,
            queryset=resolver(root, info, **args),
            request=info.context,
        ).qs
        return maybe_queryset(qs)

    def get_resolver(self, parent_resolver):
        return partial(
            self.list_resolver,
            parent_resolver,
            self.model._default_manager,
            self.filterset_class,
            self.filtering_args
        )
