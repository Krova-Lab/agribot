"""Regression checks for provenance-gated and traceable RAG retrieval."""

import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

import rag_search  # noqa: E402


class RagSearchTests(unittest.TestCase):
    def test_empty_query_does_not_call_external_services(self):
        with patch.object(rag_search.psycopg2, "connect") as connect:
            self.assertEqual(rag_search.retrieve_rag("").status, "skipped")
            connect.assert_not_called()

    def test_search_requires_approved_verified_sources_in_both_corpora(self):
        embedding = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
        model = SimpleNamespace(embed_content=MagicMock(return_value=embedding))
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = [
            ("rag_documents", 7, "IRRI water guide", "Keep the field shallow after transplanting.",
             "https://irri.org/water", "IRRI", date(2024, 1, 1), "CC BY 4.0", "Section 3, p. 12", "abc123", 0.12),
        ]

        with patch.object(rag_search, "client", SimpleNamespace(models=model)):
            with patch.object(rag_search.psycopg2, "connect", return_value=connection):
                retrieval = rag_search.retrieve_rag("rice irrigation", limit=3)

        sql, params = connection.cursor.return_value.execute.call_args.args
        self.assertIn("audit_status = 'approved'", sql)
        self.assertIn("provenance_status = 'verified'", sql)
        self.assertIn("NULLIF(BTRIM(source_url), '') IS NOT NULL", sql)
        self.assertIn("FROM knowledge_base AS kb", sql)
        self.assertEqual(params, ([0.1, 0.2], 3))
        self.assertEqual(retrieval.status, "ok")
        self.assertEqual(retrieval.sources[0].url, "https://irri.org/water")
        self.assertEqual(retrieval.sources[0].source_locator, "Section 3, p. 12")
        self.assertEqual(retrieval.sources[0].trace(1)["content_sha256"], "abc123")
        self.assertEqual(retrieval.sources[0].trace(1)["source_locator"], "Section 3, p. 12")
        self.assertIn("https://irri.org/water", rag_search.format_rag_context(retrieval.sources))
        self.assertIn("Page/section: Section 3, p. 12", rag_search.format_rag_context(retrieval.sources))
        connection.close.assert_called_once()

    def test_search_can_surface_errors_for_integration_checks(self):
        embedding = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
        model = SimpleNamespace(embed_content=MagicMock(return_value=embedding))

        with patch.object(rag_search, "client", SimpleNamespace(models=model)):
            with patch.object(rag_search.psycopg2, "connect", side_effect=rag_search.psycopg2.OperationalError("database unavailable")):
                with self.assertRaisesRegex(rag_search.psycopg2.OperationalError, "database unavailable"):
                    rag_search.retrieve_rag("rice soil", raise_on_error=True)


if __name__ == "__main__":
    unittest.main()
