"""Checks for source-manifest parsing without loading ingestion providers."""

import json
import tempfile
import unittest
from pathlib import Path

from source_metadata import load_source_manifest, source_manifest_path


class SourceMetadataTests(unittest.TestCase):
    def test_missing_manifest_keeps_document_unattributed(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "guide.pdf"
            document.touch()
            metadata, error = load_source_manifest(document)
        self.assertEqual(metadata, {})
        self.assertIsNone(error)

    def test_manifest_retains_explicit_source_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "guide.pdf"
            sidecar = source_manifest_path(document)
            sidecar.write_text(json.dumps({
                "source_title": "Rice water management",
                "source_url": "https://example.org/rice",
                "publisher": "Research Institute",
                "publication_date": "2025-04-02",
                "license": "CC BY 4.0",
                "page_or_section": "Section 4",
            }), encoding="utf-8")
            metadata, error = load_source_manifest(document)
        self.assertIsNone(error)
        self.assertEqual(metadata["source_url"], "https://example.org/rice")
        self.assertEqual(metadata["source_publisher"], "Research Institute")
        self.assertEqual(metadata["source_publication_date"], "2025-04-02")

    def test_invalid_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "guide.pdf"
            source_manifest_path(document).write_text(
                '{"source_url":"javascript:alert(1)"}', encoding="utf-8"
            )
            metadata, error = load_source_manifest(document)
        self.assertEqual(metadata, {})
        self.assertIn("HTTP(S)", error)


if __name__ == "__main__":
    unittest.main()
