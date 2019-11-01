from aristotle_mdr.contrib.serializers.concept_serializer import ConceptSerializerFactory


def concat_elems_and_remove_commas_from_iter(iterable):
    return ",".join([elem.__class__.__name__ for elem in iterable]).replace(',', '')


def create_model_api_class_dynamically(model, base_model_classes, class_attrs=None):
    """
    The purpose of this function is to create a Rest Framework View class dynamically,
    and provide a serializer to it.
    :param model: Model subclass of _concept to generate a serializer for the View.
    :param base_model_classes: Tuple of Base Classes (parent classes) for the Class returned.
    :param class_attrs: Dictionary (optional) containing class attributes and their values in the form of key-value pairs
    for our dynamically-created class.
    :return: Class.
    """

    if class_attrs is None:
        class_attrs = {}
    return type(
        model.__class__.__name__.capitalize() + concat_elems_and_remove_commas_from_iter(base_model_classes),
        base_model_classes,
        {
            "queryset": model.objects.all(),
            "serializer_class": ConceptSerializerFactory().generate_serializer_class(model),
            '__doc__': "\n{}".format(model.__doc__.replace('\n\n', '\n')),
            **class_attrs,
         }
    )
