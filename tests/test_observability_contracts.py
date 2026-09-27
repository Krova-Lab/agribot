"""Static contracts for telemetry, retention reporting, and abuse limits."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ObservabilityContractTests(unittest.TestCase):
    def test_pipeline_records_stage_telemetry_without_prompt_content(self):
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        for stage in (
            "media_download",
            "image_normalization",
            "media_interpretation",
            '"rag"',
            '"web"',
            '"response"',
            '"total"',
        ):
            self.assertIn(stage, source)
        self.assertIn('"telemetry": telemetry', source)
        self.assertNotIn('"prompt": system_prompt', source)

    def test_model_router_records_attempts_and_optional_cost(self):
        source = (ROOT / "llm_adapter.py").read_text(encoding="utf-8")
        self.assertIn('telemetry: dict | None = None', source)
        self.assertIn('"attempts"', source)
        self.assertIn('"fallback_used"', source)
        self.assertIn("KROVA_COST_PROMPT_USD_PER_1K", source)

    def test_retention_is_report_only_until_policy_is_approved(self):
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        self.assertIn("report_retention_candidates", source)
        self.assertNotIn("DELETE FROM interactions", source)
        self.assertNotIn("SET raw_user_text = NULL", source)

    def test_limits_are_configurable_and_documented(self):
        env = (ROOT / ".env.example").read_text(encoding="utf-8")
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        self.assertIn("MAX_USER_TEXT_CHARS", env)
        self.assertIn("INTERACTION_RETENTION_DAYS", env)
        self.assertIn("MAX_USER_TEXT_CHARS", source)

    def test_metrics_report_is_aggregate_only(self):
        source = (ROOT / "bin/report_metrics.py").read_text(encoding="utf-8")
        self.assertIn("percentile_cont", source)
        self.assertIn("responses_without_sources", source)
        self.assertNotIn("raw_user_text", source)
        self.assertNotIn("media_file_id", source)


if __name__ == "__main__":
    unittest.main()
