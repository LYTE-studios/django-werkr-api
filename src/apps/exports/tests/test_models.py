import uuid
from django.test import TestCase
from django.utils import timezone
from apps.exports.models import ExportFile
from apps.core.utils.formatters import FormattingUtil
from apps.authentication.utils.media_util import MediaUtil


class ExportFileModelTest(TestCase):
    def setUp(self):
        self.export_file = ExportFile.objects.create(
            name="Test Export",
            file_name="test_export.csv",
            description="Test description",
            created=timezone.now(),
        )

    def test_export_file_creation(self):
        self.assertIsInstance(self.export_file, ExportFile)
        self.assertEqual(self.export_file.name, "Test Export")
        self.assertEqual(self.export_file.file_name, "test_export.csv")
        self.assertEqual(self.export_file.description, "Test description")
        self.assertIsNotNone(self.export_file.created)

    def test_get_upload_path(self):
        path = ExportFile.get_upload_path(self.export_file, self.export_file.file_name)
        self.assertEqual(path, "exports/test_export.csv")

    def test_to_model_view(self):
        model_view = self.export_file.to_model_view()
        self.assertEqual(model_view[k_name], "Test Export")
        self.assertEqual(model_view[k_file_name], "test_export.csv")
        self.assertEqual(model_view[k_description], "Test description")
        self.assertEqual(
            model_view[k_created_at],
            FormattingUtil.to_timestamp(self.export_file.created),
        )
        self.assertEqual(
            model_view[k_file_url], MediaUtil.to_media_url(self.export_file.file.url)
        )
