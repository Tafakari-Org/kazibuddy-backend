import os
import tempfile
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .views import delete_file_from_supabase, get_file_url_from_supabase, upload_file_to_supabase

PUBLIC_BASE = "https://example.supabase.co/storage/v1/object/public/tafakari"


def fake_client(existing=(), upload_error=None, remove_error=None):
    """A stand-in Supabase client whose bucket lists `existing` file names."""
    bucket = MagicMock()
    bucket.list.return_value = [{"name": n} for n in existing]
    bucket.get_public_url.side_effect = lambda path: f"{PUBLIC_BASE}/{path}"
    # Successful SDK calls return plain data, with no `.error` attribute.
    bucket.upload.return_value = {"Key": "uploaded"}
    bucket.remove.return_value = [{"name": "removed"}]
    if upload_error:
        bucket.upload.side_effect = upload_error
    if remove_error:
        bucket.remove.side_effect = remove_error
    client = MagicMock()
    client.storage.from_.return_value = bucket
    return client, bucket


class SupabaseStorageTests(SimpleTestCase):
    """Supabase helpers, tested against a fake client — no network or real bucket involved."""

    def setUp(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            self.path = f.name
        self.addCleanup(os.remove, self.path)

    def _patch(self, client):
        p = patch("utils.views.get_supabase_client", return_value=client)
        p.start()
        self.addCleanup(p.stop)

    def test_upload_returns_public_url(self):
        client, bucket = fake_client()
        self._patch(client)
        url = upload_file_to_supabase(self.path, "cv.pdf", "documents")
        self.assertEqual(url, f"{PUBLIC_BASE}/documents/cv.pdf")
        kwargs = bucket.upload.call_args.kwargs
        self.assertEqual(kwargs["path"], "documents/cv.pdf")
        self.assertEqual(kwargs["file"], b"test content")
        self.assertEqual(kwargs["file_options"]["content-type"], "application/pdf")

    def test_upload_skips_existing_file(self):
        client, bucket = fake_client(existing=["cv.pdf"])
        self._patch(client)
        self.assertEqual(upload_file_to_supabase(self.path, "cv.pdf", "documents"), f"{PUBLIC_BASE}/documents/cv.pdf")
        bucket.upload.assert_not_called()

    def test_upload_already_exists_error_returns_url(self):
        client, _ = fake_client(upload_error=Exception("The resource already exists"))
        self._patch(client)
        self.assertEqual(upload_file_to_supabase(self.path, "a.txt", "documents"), f"{PUBLIC_BASE}/documents/a.txt")

    def test_upload_failure_raises(self):
        client, _ = fake_client(upload_error=Exception("network down"))
        self._patch(client)
        with self.assertRaisesMessage(Exception, "network down"):
            upload_file_to_supabase(self.path, "a.txt", "documents")

    def test_upload_rejects_unknown_type_and_missing_client(self):
        self._patch(fake_client()[0])
        with self.assertRaises(ValueError):
            upload_file_to_supabase(self.path, "a.exe", "binaries")
        with patch("utils.views.get_supabase_client", return_value=None), self.assertRaises(ValueError):
            upload_file_to_supabase(self.path, "a.txt", "documents")

    def test_get_file_url(self):
        self._patch(fake_client()[0])
        self.assertEqual(get_file_url_from_supabase("pic.png", "images"), f"{PUBLIC_BASE}/images/pic.png")

    def test_delete_existing_file(self):
        client, bucket = fake_client(existing=["a.txt"])
        self._patch(client)
        self.assertTrue(delete_file_from_supabase("a.txt", "documents"))
        bucket.remove.assert_called_once_with(["documents/a.txt"])

    def test_delete_missing_file_counts_as_deleted(self):
        client, bucket = fake_client(existing=[])
        self._patch(client)
        self.assertTrue(delete_file_from_supabase("gone.txt", "documents"))
        bucket.remove.assert_not_called()

    def test_delete_failure_raises(self):
        client, _ = fake_client(existing=["a.txt"], remove_error=Exception("permission denied"))
        self._patch(client)
        with self.assertRaisesMessage(Exception, "permission denied"):
            delete_file_from_supabase("a.txt", "documents")
