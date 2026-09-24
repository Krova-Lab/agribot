"""Regression checks for the live and historical RAG retrieval paths."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

import rag_search  # noqa: E402


class RagSearchTests(unittest.TestCase):
    def test_empty_query_does_not_call_external_services(self):
        with patch.object(rag_search.psycopg2, "connect") as connect:
            self.assertEqual(rag_search.search_rag(""), "")
            connect.assert_not_called()

    def test_search_uses_both_corpora_and_excludes_unreviewed_hf(self):
        embedding = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
        model = SimpleNamespace(embed_content=MagicMock(return_value=embedding))
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = [
            ("fao_soil_management.pdf", "Soil guidance", 0.1),
        ]

        with patch.object(rag_search, "client", SimpleNamespace(models=model)):
            with patch.object(rag_search.psycopg2, "connect", return_value=connection):
                result = rag_search.search_rag("rice soil", limit=3)

        sql, params = connection.cursor.return_value.execute.call_args.args
        self.assertIn("FROM rag_documents", sql)
        self.assertIn("FROM knowledge_base AS kb", sql)
        self.assertIn("audit_status = 'approved'", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("test_nul_byte.txt", params[0])
        self.assertIn("test_nul_byte.txt", params[3])
        self.assertEqual(params[2], "agri_hf_")
        self.assertEqual(params[5], "agri_hf_")
        self.assertEqual(params[-2:], ([0.1, 0.2], 3))
        self.assertEqual(result, "[fao_soil_management.pdf] Soil guidance")
        connection.close.assert_called_once()

    def test_search_can_surface_errors_for_integration_checks(self):
        embedding = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
        model = SimpleNamespace(embed_content=MagicMock(return_value=embedding))

        with patch.object(rag_search, "client", SimpleNamespace(models=model)):
            with patch.object(rag_search.psycopg2, "connect", side_effect=rag_search.psycopg2.OperationalError("database unavailable")):
                with self.assertRaisesRegex(rag_search.psycopg2.OperationalError, "database unavailable"):
                    rag_search.search_rag("rice soil", raise_on_error=True)


if __name__ == "__main__":
    unittest.main()
