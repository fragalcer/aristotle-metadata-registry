from aristotle_mdr.contrib.serializers.utils import AristotleComponentSerializer
from aristotle_ontology.models import ObjectClassSpecialisationNarrowerClass


class ObjectClassSpecialisationNarrowerClassSerializer(AristotleComponentSerializer):
    class Meta:
        model = ObjectClassSpecialisationNarrowerClass
        fields = ['order', 'narrower_class']
