from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext as _
from aristotle_mdr.utils.model_utils import aristotleComponent
import aristotle_mdr.models as MDR
"""
These models are based on the DDI3.2 and the SQBL XML formats.
"""


class AdministrationMode(MDR.unmanagedObject):
    pass


class Question(MDR.concept):
    template = "mallard_qr/question.html"
    collected_data_element = models.ForeignKey(
        MDR.DataElement,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="questions",
    )
    question_text = MDR.RichTextField(
        blank=True,
        help_text=_("The text which describes the information which is to be obtained.")
    )
    instruction_text = MDR.RichTextField(blank=True)
    # administration_modes = models.ManyToManyField(AdministrationMode,blank=True,null=True)
    estimated_seconds_response_time = models.PositiveIntegerField(
        null=True, blank=True,
        help_text=_("The estimated amount of time required to answer a question expressed in seconds.")
    )


class ResponseDomain(aristotleComponent):

    parent_field_name = 'question'

    question = models.ForeignKey(Question, related_name="response_domains", on_delete=models.CASCADE)
    value_domain = models.ForeignKey(
        MDR.ValueDomain,
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    maximum_occurrences = models.PositiveIntegerField(
        default=1,
        help_text=_("The maximum number of times a response can be included in a question")
    )
    minimum_occurrences = models.PositiveIntegerField(
        default=1,
        help_text=_("The minimum number of times a response can be included in a question")
    )
    blank_is_missing_value = models.BooleanField(default=False, help_text=_("When value is true a blank or empty variable content should be treated as a missing value."))
    order = models.PositiveSmallIntegerField(
        "Position",
        null=True,
        blank=True,
        help_text=_("If a dataset is ordered, this indicates which position this item is in a dataset.")
    )

    class Meta:
        ordering = ['order']


"""
class QuestionModule(MDR.concept):
    template = "mallard-qr/questionmodule.html"
    questions = models.ManyToManyField(Question,blank=True,null=True)
    submodules = models.ManyToManyField('QuestionModule',blank=True,null=True)
    instruction_text = MDR.RichTextField(blank=True,null=True)
    sqbl_definition = TextField(blank=True,null=True)
    administration_modes = models.ManyToManyField(AdministrationMode,blank=True,null=True)

class Questionnaire(MDR.concept):
    template = "mallard-qr/questionnaire.html"
    submodules = models.ManyToManyField(QuestionModule,blank=True,null=True)
    instructionText = MDR.RichTextField(blank=True)
    administration_modes = models.ManyToManyField(AdministrationMode,blank=True,null=True)
"""
