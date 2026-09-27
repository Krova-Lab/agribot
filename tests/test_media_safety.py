import unittest
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from media_utils import enforce_download_limit, normalize_image
import bot_telegram


class MediaSafetyTests(unittest.TestCase):
    def test_downloaded_bytes_are_checked_even_without_provider_metadata(self):
        with self.assertRaises(ValueError):
            enforce_download_limit(b"12345", 4, "Image")

    def test_image_is_normalized_to_a_bounded_jpeg(self):
        from PIL import Image
        import io

        source = io.BytesIO()
        Image.new("RGB", (1600, 900), "green").save(source, format="PNG")
        normalized = normalize_image(source.getvalue(), 10 * 1024 * 1024)
        with Image.open(io.BytesIO(normalized)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 1024)

    def test_media_cache_cleanup_removes_only_expired_files(self):
        with tempfile.TemporaryDirectory() as image_dir, tempfile.TemporaryDirectory() as audio_dir:
            old_image = Path(image_dir) / "old.jpg"
            new_audio = Path(audio_dir) / "new.ogg"
            old_image.write_bytes(b"old")
            new_audio.write_bytes(b"new")
            old_timestamp = time.time() - 7200
            os.utime(old_image, (old_timestamp, old_timestamp))

            with patch.object(bot_telegram, "IMAGE_CACHE_DIR", image_dir), patch.object(
                bot_telegram, "AUDIO_CACHE_DIR", audio_dir
            ), patch.object(bot_telegram, "MEDIA_CACHE_RETENTION_SECONDS", 3600):
                bot_telegram.purge_media_cache()

            self.assertFalse(old_image.exists())
            self.assertTrue(new_audio.exists())


if __name__ == "__main__":
    unittest.main()
