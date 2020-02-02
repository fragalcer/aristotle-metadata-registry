# Start of the question model

import aristotle_mdr
from django.db import models


class Question(aristotle_mdr.models.concept):
    template = "extension_test/concepts/question.html"
    questionText = models.TextField(blank=True, null=True)
    responseLength = models.PositiveIntegerField(blank=True, null=True)
    collectedDataElement = models.ForeignKey(
        aristotle_mdr.models.DataElement,
        related_name="questions",
        null=True,
        blank=True,
        on_delete=models.deletion.CASCADE,
    )


# End of the question model

class Questionnaire(aristotle_mdr.models.concept):
    # Questionnaire is a test of a lazy developer who has done the bare minimum
    # To get an object in the system. This is a test of how little a dev can to
    # get a functional object. Ideally the string 'Questionnaire' should exist only here.
    edit_page_excludes = ['questions', 'respondent_classes', 'targetrespondentclass']
    through_edit_excludes = ['respondent_classes']
    admin_page_excludes = ['respondent_classes', 'targetrespondentclass']
    # template = "extension_test/concepts/question.html"  # Blank to test default template
    questions = models.ManyToManyField(
        Question,
        related_name="questionnaires",
        blank=True
    )
    respondent_classes = models.ManyToManyField(
        aristotle_mdr.models.ObjectClass,
        through='TargetRespondentClass'
    )
    start_date = models.DateField(
        blank=True,
        null=True,
        help_text='Date the questionnaire was run from'
    )
    end_date = models.DateField(
        blank=True,
        null=True,
        help_text='Date the questionnaire was run until'
    )

    # Start of get_download_items
    def get_download_items(self):
        return [
            self.questions.all().order_by('name'),
            aristotle_mdr.models.DataElement.objects.filter(questions__questionnaires=self).order_by('name')
        ]
    # End of get_download_items


# This is a pretty contrived testing model
class TargetRespondentClass(aristotle_mdr.models.aristotleComponent):
    @property
    def parentItem(self):
        return self.questionnaire

    questionnaire = models.ForeignKey('Questionnaire', on_delete=models.deletion.CASCADE)
    respondent_class = models.ForeignKey(aristotle_mdr.models.ObjectClass, on_delete=models.deletion.CASCADE)
    rationale = models.TextField(blank=True, null=True)
