"""PDF page locators are retained through chunking for source-level citation."""

import os
import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

with patch.dict(sys.modules, {
    "pytesseract": MagicMock(),
    "pdf2image": MagicMock(),
}):
    ingest_files = importlib.import_module("ingest_files")


class IngestionLocatorTests(unittest.TestCase):
    def test_chunk_spanning_pages_records_both_pdf_pages(self):
        chunks = ingest_files.chunk_pages(
            ["A" * 100, "B" * 100], base_locator="Chapter 4", chunk_size=150, overlap=0
        )

        self.assertEqual(chunks[0][1], "Chapter 4; PDF pp. 1–2")
        self.assertEqual(chunks[1][1], "Chapter 4; PDF p. 2")

    def test_pdf_extraction_preserves_individual_page_text(self):
        first_page = "First page content " * 12
        second_page = "Second page content " * 12
        pages = [type("Page", (), {"extract_text": lambda self: first_page})(),
                 type("Page", (), {"extract_text": lambda self: second_page})()]
        with patch.object(ingest_files, "PdfReader", return_value=type("Reader", (), {"pages": pages})()):
            self.assertEqual(
                ingest_files.extract_pages_from_file("manual.pdf"),
                [first_page.strip(), second_page.strip()],
            )


if __name__ == "__main__":
    unittest.main()
