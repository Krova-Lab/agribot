import unittest

from media_utils import enforce_download_limit, normalize_image


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


if __name__ == "__main__":
    unittest.main()
