from aristotle_mdr_graphql.types import AristotleObjectType, AristotleConceptObjectType
from aristotle_mdr.models import _concept
from graphene_django.types import DjangoObjectType
import graphene
from aristotle_mdr_graphql.resolvers import aristotle_resolver
from textwrap import dedent


def inline_type_from_model(meta_model, filter_fields=None, description=None):

    new_model_name = meta_model.__name__ + 'Node'
    description = description or dedent(meta_model.__doc__)

    _filter_fields = []
    if filter_fields is not None:
        _filter_fields = filter_fields

    meta_class = type('Meta', (object, ), dict(
        model=meta_model,
        description=description,
        filter_fields=_filter_fields,
        default_resolver=aristotle_resolver,
    ))
    dynamic_class = type(new_model_name, (DjangoObjectType, ), dict(Meta=meta_class))
    return dynamic_class


def type_from_model(meta_model, filter_fields=None, description=None):

    new_model_name = meta_model.__name__ + 'Node'
    description = description or dedent(meta_model.__doc__)

    _filter_fields = []
    if filter_fields is not None:
        _filter_fields = filter_fields

    meta_class = type('Meta', (object, ), dict(
        model=meta_model,
        description=description,
        filter_fields=_filter_fields,
        interfaces=(graphene.relay.Node, ),
        default_resolver=aristotle_resolver,
    ))
    dynamic_class = type(new_model_name, (AristotleObjectType, ), dict(Meta=meta_class))
    return dynamic_class


def type_from_concept_model(meta_model, filter_fields=None, extra_filter_fields=[], resolver=aristotle_resolver, meta_kwargs={}):
    assert issubclass(meta_model, _concept)
    assert type(extra_filter_fields) in [list, dict]

    new_model_name = meta_model.__name__ + 'Node'
    description = dedent(meta_model.__doc__)
    _filter_fields = {
        'name': ['exact', 'icontains', 'iexact'],
        'uuid': ['exact'],
    }
    
    if type(extra_filter_fields) is list:
        extra_filter_fields = dict([(key, ['exact']) for key in extra_filter_fields])
    
    if filter_fields is not None:
        _filter_fields = filter_fields
    if extra_filter_fields:
        _filter_fields.update(extra_filter_fields)

    meta_kwargs.update(dict(
        model=meta_model,
        description=description,
        filter_fields=_filter_fields,
        interfaces=(graphene.relay.Node, ),
        default_resolver=resolver,
    ))

    meta_class = type('Meta', (object, ), meta_kwargs)
    dynamic_class = type(new_model_name, (AristotleConceptObjectType, ), dict(Meta=meta_class))
    
    return dynamic_class
