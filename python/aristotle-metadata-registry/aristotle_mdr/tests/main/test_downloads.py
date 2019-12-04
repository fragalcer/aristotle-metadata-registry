from django.test import TestCase, tag, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from django.core import mail

from aristotle_bg_workers.tasks import download
from aristotle_mdr import models
from aristotle_mdr.downloader import HTMLDownloader, DocxDownloader
from aristotle_mdr.tests.utils import AristotleTestUtils, AsyncResultMock, FakeDownloader

import datetime
from unittest.mock import patch, MagicMock
from unittest import skip


@override_settings(
    ARISTOTLE_SETTINGS={
        'DOWNLOAD_OPTIONS': {'DOWNLOADERS': ['aristotle_mdr.tests.utils.FakeDownloader']},
        'BULK_ACTIONS': ['aristotle_mdr.forms.bulk_actions.BulkDownloadForm']
    }
)
class DownloadsTestCase(AristotleTestUtils, TestCase):
    """
    Testing downloads views and task
    """

    def setUp(self):
        super().setUp()
        self.item = models.ObjectClass.objects.create(
            name='Pokemon',
            definition='Pocket Monsters',
            submitter=self.editor
        )
        self.item2 = models.Property.objects.create(
            name='Defense',
            definition='Defense',
            submitter=self.editor
        )
        self.item3 = models.DataElementConcept.objects.create(
            name='Pokemon - Defense',
            definition='A pokemons defense',
            submitter=self.editor
        )

    def setupFakeTaskCreator(self, mock_task_creator):
        fakeResult = AsyncResultMock(20)
        mock_task_creator.return_value = fakeResult

    def post_dl_options(self, querystring):
        url = reverse('aristotle:download_options', args=['fake']) + querystring
        postdata = {
            'include_supporting': True,
            'email_copy': True
        }

        response = self.client.post(url, postdata)
        return response

    @patch('aristotle_bg_workers.tasks.get_download_class')
    def test_download_task(self, fake_get_dl_class):
        # Setup mocks
        fake_dl_class = MagicMock()
        fake_get_dl_class.return_value = fake_dl_class
        # Call task
        result = download('fake', [self.item.id], self.editor.id)
        # Check mocks
        self.assertIsNotNone(result)
        fake_dl_class.assert_called_once_with([self.item.id], self.editor.id, {})
        fake_dl_class().download.assert_called_once()

    def test_dl_options_get_no_items(self):
        url = reverse('aristotle:download_options', args=['fake'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_dl_options_get_with_items(self):
        object_class = models.ObjectClass.objects.create(
            name='Pokemon',
            definition='Pocket Monsters',
            submitter=self.editor,
        )
        url = reverse('aristotle:download_options', args=['fake']) + f'?items={object_class.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dl_options_redirect(self):
        response = self.post_dl_options('?items=1')
        self.assertEqual(response.status_code, 302)

        expected_url = reverse('aristotle:download', args=['fak', '1'])
        self.assertEqual(response.url, expected_url)

    def test_dl_options_redirect(self):
        response = self.post_dl_options('?items=1&items=2')
        self.assertEqual(response.status_code, 302)

        expected_url = reverse('aristotle:bulk_download', args=['fake']) + '?items=1&items=2'
        self.assertEqual(response.url, expected_url)

    def test_dl_options_stores_options(self):
        response = self.post_dl_options('?items=4')
        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            self.client.session['download_options'],
            {
                'include_supporting': True,
                'include_related': False,
                'title': '',
                'registration_authority': None,
                'registration_status': None
            }
        )

    @patch('aristotle_mdr.views.downloads.download.delay')
    def test_download_view_starts_task(self, mock_task_creator):
        self.setupFakeTaskCreator(mock_task_creator)
        response = self.reverse_get(
            'aristotle:download',
            reverse_args=['fake', self.item.id],
            status_code=200
        )

        mock_task_creator.assert_called_once_with('fake', [self.item.id], None, {'CURRENT_HOST': 'http://testserver'})

    @patch('aristotle_mdr.views.downloads.download.delay')
    def test_bulk_download_view_starts_task(self, mock_task_creator):
        self.setupFakeTaskCreator(mock_task_creator)
        url = reverse('aristotle:bulk_download', args=['fake'])
        url += '?items={}&items={}&items={}'.format(self.item.id, self.item2.id, self.item3.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        id_list = [self.item.id, self.item2.id, self.item3.id]
        mock_task_creator.assert_called_once_with('fake', id_list, None, {'CURRENT_HOST': 'http://testserver'})

    def test_download_404_when_invalid_type(self):
        self.reverse_get(
            'aristotle:download',
            reverse_args=['jpg', self.item.id],
            status_code=404
        )

    @patch('aristotle_mdr.views.downloads.download.delay')
    def test_task_started_with_options(self, mock_task_creator):
        self.setupFakeTaskCreator(mock_task_creator)
        options = {
            'include_supporting': True,
            'email_copy': True,
            'CURRENT_HOST': 'http://testserver',
        }

        session = self.client.session
        session['download_options'] = options
        session.save()

        response = self.reverse_get(
            'aristotle:download',
            reverse_args=['fake', self.item.id],
            status_code=200
        )

        mock_task_creator.assert_called_once_with('fake', [self.item.id], None, options)

    @tag('bulk_download')
    def test_bulk_download_redirects(self):
        self.login_editor()

        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_mdr.forms.bulk_actions.BulkDownloadForm',
                'items': [self.item.id, self.item2.id],
                "download_type": 'fake',
                'confirmed': 'confirmed',
            }
        )

        self.assertEqual(response.status_code, 302)
        expected_get_params = '?items={}&items={}'.format(self.item.id, self.item2.id)
        expected_url = reverse('aristotle:download_options', args=['fake']) + expected_get_params
        self.assertEqual(response.url, expected_url)


class DownloaderTestCase(AristotleTestUtils, TestCase):
    """
    Testing functionality defined in the base downloader
    """

    def setUp(self):
        super().setUp()
        self.item = models.ObjectClass.objects.create(
            name='Pokemon',
            definition='Pocket Monsters',
            submitter=self.editor
        )
        self.item2 = models.Property.objects.create(
            name='Defense',
            definition='Defense',
            submitter=self.editor
        )
        self.item3 = models.DataElementConcept.objects.create(
            name='Pokemon - Defense',
            definition='A pokemons defense',
            submitter=self.editor
        )
        self.item4 = models.Property.objects.create(
            name='Attack',
            definition='Attack',
            submitter=self.viewer
        )

    def test_file_path_auth_user(self):
        downloader = FakeDownloader([self.item.id], self.editor.id, {'include_supporting': True})
        path = downloader.get_filepath()
        self.assertRegex(path, '[0-9]+/[0-9a-f]+/download.fak')

    def test_file_path_anon_user(self):
        # Make public so we dont get a permission denied
        self.make_item_public(self.item, self.ra)
        # Setup downloader get path
        downloader = FakeDownloader([self.item.id], None, {'include_supporting': True})
        path = downloader.get_filepath()
        self.assertRegex(path, 'anon/[0-9a-f]+/download.fak')

    @override_settings(DOWNLOAD_CACHING=True)
    def test_file_not_created_if_can_be_retrieved(self):
        fake_url = 'http://www.example.com/existing/file.fak'
        with patch.object(FakeDownloader, 'retrieve_file', return_value=fake_url):
            downloader = FakeDownloader([self.item.id], self.editor.id, {'include_supporting': True})
            url = downloader.download()
            self.assertEqual(url, fake_url)

    @override_settings(DOWNLOAD_CACHING=True)
    def test_dont_retrieve_file_if_item_modified(self):
        item_created = self.item.created
        with patch.object(FakeDownloader, 'get_storage') as fake_storage:
            # File modified after item
            fake_storage().get_modified_time.return_value = item_created + datetime.timedelta(seconds=1000)
            fake_storage().url.return_value = 'http://www.example.com/file.txt'
            downloader = FakeDownloader([self.item.id], self.editor.id, {'include_supporting': True})
            url = downloader.retrieve_file('file.txt')

        self.assertEqual(url, 'http://www.example.com/file.txt')

    @override_settings(DOWNLOAD_CACHING=True)
    def test_retrieve_file_if_item_not_modified(self):
        item_created = self.item.created
        with patch.object(FakeDownloader, 'get_storage') as fake_storage:
            # File modified before item
            fake_storage().get_modified_time.return_value = item_created - datetime.timedelta(seconds=1000)
            fake_storage().url.return_value = 'http://www.example.com/file.txt'
            downloader = FakeDownloader([self.item.id], self.editor.id, {'include_supporting': True})
            url = downloader.retrieve_file('file.txt')

        self.assertEqual(url, None)

    def test_items_restricted_to_visible_only(self):
        downloader = FakeDownloader([self.item.id, self.item4.id], self.viewer.id, {})
        self.assertEqual(downloader.numitems, 1)
        self.assertEqual(downloader.items[0].id, self.item4.id)

    def test_exception_raised_if_no_items_visible(self):
        with self.assertRaises(PermissionDenied):
            downloader = FakeDownloader([self.item.id], self.viewer.id, {})

    @skip('Removed direct email attachments')
    def test_email_file_direct(self):
        downloader = FakeDownloader([self.item.id], self.editor.id, {})
        f = ContentFile('MyFile')
        size = f.size
        f.close()
        downloader.email_file(f, size, 'https://example.com/file.txt')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(len(message.attachments), 1)
        content = message.attachments[0][1]
        self.assertEqual(content, 'MyFile')

    def test_email_file(self):
        downloader = FakeDownloader([self.item.id], self.editor.id, {'CURRENT_HOST': 'http://testserver'})
        f = ContentFile('MyFile')
        size = f.size
        f.close()
        downloader.email_file(f, size, 'https://example.com/file.txt')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(len(message.attachments), 0)
        self.assertTrue('https://example.com/file.txt' in message.body)

        expected_regen_url = reverse('aristotle:download_options', args=['fake'])\
            + '?items=' + str(self.item.id)
        self.assertTrue(expected_regen_url in message.body)


@override_settings(ARISTOTLE_SETTINGS={'DOWNLOAD_OPTIONS': {'DOWNLOADERS': ['aristotle_mdr.downloaders.HTMLDownloader']}})
class TestHTMLDownloader(AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.animal = models.ObjectClass.objects.create(
            name='Animal',
            definition='An animal or animal like object',
            submitter=self.editor
        )
        self.speed = models.Property.objects.create(
            name='Speed',
            definition='Quickness',
            submitter=self.editor
        )
        self.forbidden_speed = models.Property.objects.create(
            name='Speed',
            definition='Quickness'
            # No submitter so forbidden
        )

        self.aspeed = models.DataElementConcept.objects.create(
            name='Animal - Speed',
            definition='An animals speed',
            submitter=self.editor
        )

    def test_generates_html_bytes(self):
        downloader = HTMLDownloader([self.animal.id], self.editor.id, {})
        html = downloader.get_html()
        self.assertEqual(type(html), bytes)

    def test_creates_file(self):
        downloader = HTMLDownloader([self.animal.id], self.editor.id, {})
        fileobj = downloader.create_file()
        self.assertTrue(fileobj.size > 0)

    def test_title_added(self):
        test_title = 'The single greatest piece of metadata content of the modern era'
        downloader = HTMLDownloader([self.animal.id], self.editor.id, {'title': test_title})
        context = downloader.get_context()
        self.assertTrue('title' in context['options'])
        self.assertEqual(context['options']['title'], test_title)

        html = downloader.get_html().decode()
        self.assertTrue(test_title in html)

    def test_content_exists_in_bulk_html_download_on_permitted_items(self):
        downloader = HTMLDownloader([self.animal.id, self.aspeed.id], self.editor.id, {})
        html = downloader.get_html().decode()
        self.assertTrue(self.animal.definition in html)
        self.assertTrue(self.aspeed.definition in html)

    def test_content_not_exists_in_bulk_html_download_on_forbidden_items(self):
        downloader = HTMLDownloader([self.animal.id, self.aspeed.id, self.forbidden_speed.id], self.editor.id, {})
        html = downloader.get_html().decode()
        self.assertTrue(self.animal.definition in html)
        self.assertTrue(self.aspeed.definition in html)
        self.assertFalse(self.forbidden_speed.definition in html)

    def test_sub_item_list_single_download(self):

        self.aspeed.objectClass = self.animal
        self.aspeed.property = self.speed
        self.aspeed.save()

        downloader = HTMLDownloader([self.aspeed.id], self.editor.id, {"include_supporting": True})

        context = downloader.get_context()
        self.assertCountEqual(
            context['subitems']['aristotle_mdr.objectclass'].items,
            [self.animal]
        )

        self.assertCountEqual(
            context['subitems']['aristotle_mdr.property'].items,
            [self.speed]
        )

    def test_item_with_supersedes_download(self):
        # ra = models.RegistrationAuthority.objects.create(name='RA', definition='RA')
        old_animal = models.ObjectClass.objects.create(
            name='Old animal',
            definition='animal'
        )
        new_animal = models.ObjectClass.objects.create(
            name='New animal',
            definition='animal'
        )
        models.SupersedeRelationship.objects.create(
            older_item=old_animal,
            newer_item=self.animal,
            registration_authority=self.ra
        )
        models.SupersedeRelationship.objects.create(
            older_item=self.animal,
            newer_item=new_animal,
            registration_authority=self.ra
        )

        downloader = HTMLDownloader([self.animal.id], self.su.id, {})
        html = downloader.get_html().decode()
        self.assertTrue('Old animal' in html)
        self.assertTrue('New animal' in html)

    def test_de_download(self):
        # Link DEC
        self.aspeed.objectClass = self.animal
        self.aspeed.property = self.speed
        self.aspeed.save()

        # Make editor the speed submitter
        self.speed.submitter = self.editor
        self.speed.save()

        # Create DE
        de = models.DataElement.objects.create(
            name='Animal - Speed, Code',
            definition='Animal speed code',
            submitter=self.editor,
            dataElementConcept=self.aspeed
        )

        # Download item
        downloader = HTMLDownloader([de.id], self.editor.id, {})
        html = downloader.get_html().decode()

        # Make sure there is content
        self.assertTrue(len(html) > 0)

        # Make sure all items were displayed
        self.assertFalse('You dont have permission' in html)


@override_settings(ARISTOTLE_SETTINGS={'DOWNLOAD_OPTIONS': {'DOWNLOADERS': ['aristotle_mdr.downloaders.DocxDownloader']}})
class DocxDownloaderTestCase(AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.item = models.DataElement.objects.create(
            name='Onix',
            definition='Big rock boi',
            submitter=self.editor
        )

    @tag('docx')
    @skip('pandoc isnt installed on all test environments')
    def test_docx_downloader_generates_file(self):
        downloader = DocxDownloader([self.item.id], self.editor.id, {})
        fileobj = downloader.create_file()
        self.assertTrue(fileobj.size > 0)
