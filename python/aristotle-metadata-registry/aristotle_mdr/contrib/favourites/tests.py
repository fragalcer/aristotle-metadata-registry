from django.test import TestCase, tag
from aristotle_mdr.tests.utils import AristotleTestUtils
from aristotle_mdr import models as mdr_models
from aristotle_mdr.contrib.favourites import models
from aristotle_mdr.utils import url_slugify_concept
from django.contrib.messages import get_messages

@tag('favourites')
class FavouritesTestCase(AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.timtam = mdr_models.ObjectClass.objects.create(
            name='Tim Tam',
            definition='Chocolate covered biscuit',
            submitter=self.editor
        )
        self.tastiness = mdr_models.Property.objects.create(
            name='Tastiness',
            definition='How good an item tastes',
            submitter=self.editor
        )
        self.ttt = mdr_models.DataElementConcept(
            name='Tim Tam - Tastiness',
            definition='Tim Tam - Tastiness',
            objectClass=self.timtam,
            property=self.tastiness,
            submitter=self.editor
        )

    def check_favourite(self, user, item, status):
        favourited = models.Favourite.objects.filter(
            item_id=item.id,
            tag__primary=True,
            tag__profile=user.profile
        ).exists()
        return (favourited == status)

    def test_toggle_favourite_function_on(self):

        self.login_editor()
        self.check_favourite(self.editor, self.timtam, False)

        self.editor.profile.toggleFavourite(self.timtam)

        self.check_favourite(self.editor, self.timtam, True)

    def test_toggle_favourite_function_off(self):

        self.login_editor()
        self.check_favourite(self.editor, self.timtam, False)

        self.editor.profile.toggleFavourite(self.timtam)

        self.check_favourite(self.editor, self.timtam, True)

        self.editor.profile.toggleFavourite(self.timtam)

        self.check_favourite(self.editor, self.timtam, False)

    def test_toggle_favourite_on_view(self):

        self.login_editor()
        self.check_favourite(self.editor, self.timtam, False)

        response = self.reverse_get(
            'aristotle_favourites:toggleFavourite',
            reverse_args=[self.timtam.id],
            status_code=302
        )
        self.assertEqual(response.url, url_slugify_concept(self.timtam))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages[1].message.startswith('Tim Tam added to favourites'))

        self.check_favourite(self.editor, self.timtam, True)

    def test_toggle_favourite_off_view(self):

        primtag = models.Tag.objects.create(
            profile=self.editor.profile,
            name='',
            primary=True
        )
        models.Favourite.objects.create(
            tag=primtag,
            item=self.timtam
        )

        self.login_editor()
        self.check_favourite(self.editor, self.timtam, True)

        response = self.reverse_get(
            'aristotle_favourites:toggleFavourite',
            reverse_args=[self.timtam.id],
            status_code=302
        )
        self.assertEqual(response.url, url_slugify_concept(self.timtam))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages[1].message.startswith('Tim Tam removed from favourites'))

        self.check_favourite(self.editor, self.timtam, False)

    def test_toggle_non_viewable(self):

        self.login_viewer()

        response = self.reverse_get(
            'aristotle_favourites:toggleFavourite',
            reverse_args=[self.timtam.id],
            status_code=403
        )
