from aristotle_mdr_api.v4.rules import serializers
from aristotle_mdr_api.v4.permissions import AuthCanViewEdit
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from aristotle_mdr.contrib.validators import models


class CreateRARules(CreateAPIView):
    """Create RA Specific Rules"""
    permission_classes = (AuthCanViewEdit,)
    serializer_class = serializers.RARuleSerializer


class RetrieveUpdateRARules(RetrieveUpdateAPIView):
    """Retrieve and update RA Specific Rules"""
    permission_classes = (AuthCanViewEdit,)
    serializer_class = serializers.RARuleSerializer
    queryset = models.RAValidationRules.objects.all()


class RetrieveUpdateRegistryRules(RetrieveUpdateAPIView):
    """
    Retrieve and Update registry wide rules
    There is only one registry rules object which is auto created
    """
    permission_classes = (AuthCanViewEdit,)
    serializer_class = serializers.RegistryRuleSerializer

    def get_object(self):
        obj = models.RegistryValidationRules.objects.first()
        if obj is None:
            obj = models.RegistryValidationRules.objects.create()

        # Check permission
        self.check_object_permissions(self.request, obj)
        return obj
