"""Guardrails for Cambodia scope and calibrated agricultural follow-up."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdvisoryCalibrationPromptTests(unittest.TestCase):
    def test_public_prompt_config_has_non_blocking_cambodia_default(self):
        config = json.loads((ROOT / "config/prompts.example.json").read_text(encoding="utf-8"))
        rules = "\n".join(config["zero_hallucination_rules"])
        self.assertIn("default geographic scope", rules)
        self.assertIn("must never block", rules)
        self.assertIn("explicitly stated in text or intelligible audio", rules)

    def test_runtime_prompt_calibrates_region_and_plot_precision(self):
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        self.assertIn("Geographic precision is graded, not binary", source)
        self.assertIn("soil, water regime, elevation, microclimate", source)
        self.assertIn("Never invent coordinates, a default city", source)
        self.assertIn("Before stating any exact number, range, dose", source)
        self.assertIn("A plausible number from model knowledge is still unverified", source)

    def test_runtime_prompt_requests_only_material_missing_information(self):
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        self.assertIn("could materially change the diagnosis, recommendation, or safety", source)
        self.assertIn("label the answer provisional", source)
        self.assertIn("high-risk chemical dose", source)

    def test_runtime_prompt_does_not_recycle_previous_assistant_output_as_evidence(self):
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        self.assertIn("previous assistant output is intentionally omitted", source)
        self.assertIn("Recent user messages are conversational context only, not verified evidence", source)
        self.assertNotIn("Prior Advisor Response:", source)

    def test_runtime_prompt_preserves_user_facing_uncertainty(self):
        source = (ROOT / "bot_telegram.py").read_text(encoding="utf-8")
        self.assertIn("do not expose internal RAG wording", source)
        self.assertIn("Give the useful general guidance first", source)


if __name__ == "__main__":
    unittest.main()
