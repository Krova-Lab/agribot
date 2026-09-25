"""Source-level regression checks for release and provenance safeguards."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_e2e_runner_returns_a_failing_exit_code(self):
        source = (ROOT / "bin/test_full_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("return bool(all_ok)", source)
        self.assertIn("SystemExit(0 if run_e2e_suite() else 1)", source)

    def test_ci_stops_on_schema_errors(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("ON_ERROR_STOP=1", workflow)
        self.assertIn("test -f schema.sql", workflow)

    def test_failed_ingestion_moves_the_provenance_sidecar(self):
        source = (ROOT / "ingest_files.py").read_text(encoding="utf-8")
        failure_block = source[source.index("except Exception as e:"):]
        self.assertIn("move_source_manifest(filepath, FAILED_DIR)", failure_block)

    def test_legacy_ingestion_cannot_write_to_the_database(self):
        source = (ROOT / "ingest.py").read_text(encoding="utf-8")
        self.assertIn("legacy ingestion path is disabled", source)
        self.assertNotIn("INSERT INTO rag_documents", source)


if __name__ == "__main__":
    unittest.main()
