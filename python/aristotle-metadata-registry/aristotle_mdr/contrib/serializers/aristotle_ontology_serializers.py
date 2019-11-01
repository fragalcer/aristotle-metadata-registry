from aristotle_mdr.contrib.serializers.utils import SubSerializer
from aristotle_ontology.models import ObjectClassSpecialisationNarrowerClass


class ObjectClassSpecialisationNarrowerClassSerializer(SubSerializer):
    class Meta:
        model = ObjectClassSpecialisationNarrowerClass
        fields = ['order', 'narrower_class']
