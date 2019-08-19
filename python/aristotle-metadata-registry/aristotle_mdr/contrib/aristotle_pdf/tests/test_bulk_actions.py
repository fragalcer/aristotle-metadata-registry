from django.urls import reverse
from django.test import TestCase
import aristotle_mdr.models as models


from aristotle_mdr.tests.utils import store_taskresult, get_download_result
from aristotle_mdr.contrib.aristotle_pdf.downloader import PDFDownloader
from aristotle_mdr.tests.main.test_bulk_actions import BulkActionsTest

import datetime
from mock import patch
from unittest import skip


@skip('Quick pdf action disabled temporarily')
class QuickPDFDownloadTests(BulkActionsTest, TestCase):

    def setUp(self):
        super().setUp()
        self.celery_result = None
        self.patcher1 = patch('aristotle_pdf.downloader.PDFDownloader.bulk_download.delay')
        self.patcher2 = patch('aristotle_mdr.views.downloads.async_result')
        self.downloader_download = self.patcher1.start()
        self.async_result = self.patcher2.start()
        self.downloader_download.side_effect = self.pdf_bulk_download_cache
        self.async_result.side_effect = self.pdf_download_task_retrieve

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()

    def pdf_bulk_download_cache(self, properties, iids):
        PDFDownloader.bulk_download(properties, iids)

        return store_taskresult()

    def pdf_download_task_retrieve(self, iid):
        """
        Using taskResult to manage the celery tasks
        :return:
        """
        if not self.celery_result:
            # Creating an instance of fake Celery `AsyncResult` object
            self.celery_result = get_download_result(iid)
        return self.celery_result

    def test_bulk_quick_pdf_download_on_permitted_items(self):
        self.login_editor()

        self.assertEqual(self.editor.profile.favourites.count(), 0)
        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_pdf.bulk_actions.QuickPDFDownloadForm',
                'items': [self.item1.id, self.item2.id],
            }
        )
        self.assertEqual(response.status_code, 302)

    def test_bulk_quick_pdf_download_on_forbidden_items(self):
        self.login_editor()

        self.assertEqual(self.editor.profile.favourites.count(), 0)
        response = self.client.post(
            reverse('aristotle:bulk_action'),
            {
                'bulkaction': 'aristotle_pdf.bulk_actions.QuickPDFDownloadForm',
                'items': [self.item1.id, self.item4.id],
            },
            follow=True
        )
        self.assertEqual(len(response.redirect_chain), 2)
        self.assertEqual(response.redirect_chain[0][1], 302)
