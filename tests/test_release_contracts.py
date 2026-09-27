"""Source-level regression checks for release and provenance safeguards."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_e2e_runner_returns_a_failing_exit_code(self):
        source = (ROOT / "bin/test_full_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("return bool(all_ok)", source)
        self.assertIn("SystemExit(0 if run_e2e_suite() else 1)", source)

    def test_ci_schema_setup_is_strict_when_present(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        if "Setup Database Schema" in workflow:
            self.assertIn("ON_ERROR_STOP=1", workflow)
            self.assertIn("test -f schema.sql", workflow)
            self.assertIn("migrations/20260925_response_preferences.sql", workflow)
            self.assertIn("migrations/20260929_request_rate_limits.sql", workflow)

    def test_schema_and_rag_contract_use_the_same_embedding_dimension(self):
        contract = (ROOT / "migrations/20260927_rag_schema_contract.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("requires vector(3072)", contract)
        self.assertIn("knowledge_base_exists", contract)
        schema_path = ROOT / "schema.sql"
        if schema_path.exists():
            schema = schema_path.read_text(encoding="utf-8")
            self.assertIn("embedding public.vector(3072)", schema)
            self.assertIn("embedding::public.halfvec(3072)", schema)

    def test_production_rag_schema_excludes_the_legacy_corpus(self):
        schema = (ROOT / "migrations/20260928_production_rag_schema.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS public.rag_documents", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS public.interactions", schema)
        self.assertIn("production_unique_interaction_review", schema)
        self.assertIn("prod_rag_documents_embedding_idx", schema)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS public.knowledge_base", schema)

    def test_ci_has_a_clean_production_schema_rehearsal(self):
        workflow_path = ROOT / ".github/workflows/ci.yml"
        if not workflow_path.exists():
            self.skipTest("The public mirror does not include the private schema CI workflow")
        workflow = workflow_path.read_text(encoding="utf-8")
        if "Setup Database Schema" not in workflow:
            self.skipTest("The public mirror uses its separate public CI workflow")
        self.assertIn("Verify dedicated production schema from scratch", workflow)
        self.assertIn("createdb", workflow)
        self.assertIn("migrations/20260925_production_bot_schema.sql", workflow)
        self.assertIn("migrations/20260928_production_rag_schema.sql", workflow)
        self.assertIn("to_regclass('public.knowledge_base')", workflow)
        self.assertIn("dropdb", workflow)

    def test_failed_ingestion_moves_the_provenance_sidecar(self):
        source = (ROOT / "ingest_files.py").read_text(encoding="utf-8")
        failure_block = source[source.index("except Exception as e:"):]
        self.assertIn("move_source_manifest(filepath, FAILED_DIR)", failure_block)

    def test_legacy_ingestion_cannot_write_to_the_database(self):
        source = (ROOT / "ingest.py").read_text(encoding="utf-8")
        self.assertIn("legacy ingestion path is disabled", source)
        self.assertNotIn("INSERT INTO rag_documents", source)

    def test_only_approved_reviews_can_enter_the_rag_dropzone(self):
        source = (ROOT / "api_server.py").read_text(encoding="utf-8")
        self.assertIn("r.status IN ('validated', 'corrected')", source)


if __name__ == "__main__":
    unittest.main()
