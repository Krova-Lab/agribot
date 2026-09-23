"""Fast regression checks that do not require external services."""

import unittest

from config.prompt_loader import load_prompts, render_prompt
from location_context import build_location_context, soil_source_for_audit
from telegram_format import to_telegram_plain_text
from ingest_rag import ingest as legacy_ingest


class PromptSmokeTests(unittest.TestCase):
    def test_public_prompts_are_loadable(self):
        prompts = load_prompts()
        self.assertIn("system_prompt", prompts)
        self.assertTrue(prompts["system_prompt"])

    def test_render_prompt_replaces_named_values(self):
        self.assertEqual(render_prompt("Hello {name}", name="Krova"), "Hello Krova")


class PilotSafeguardTests(unittest.TestCase):
    def test_no_location_does_not_fetch_local_data(self):
        def unexpected_lookup(_lat, _lon):
            self.fail("Local APIs must not be called without user coordinates")

        lat, lon, soil, weather, region = build_location_context(
            None, unexpected_lookup, unexpected_lookup
        )
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertIn("Unavailable", soil)
        self.assertIn("Unavailable", weather)
        self.assertIn("Cambodia", region)
        self.assertNotIn("Phnom Penh", region)
        self.assertIsNone(soil_source_for_audit(soil))

    def test_shared_coordinates_enable_local_data(self):
        calls = []

        def lookup(lat, lon):
            calls.append((lat, lon))
            return {"ok": True}

        lat, lon, soil, weather, region = build_location_context(
            (13.1, 103.2), lookup, lookup
        )
        self.assertEqual((lat, lon), (13.1, 103.2))
        self.assertEqual(calls, [(13.1, 103.2), (13.1, 103.2)])
        self.assertEqual(soil, {"ok": True})
        self.assertEqual(weather, {"ok": True})
        self.assertIn("user-shared", region)

    def test_soil_audit_source_requires_structured_data(self):
        self.assertEqual(soil_source_for_audit({"source": "SoilGrids-Live"}), "SoilGrids-Live")
        self.assertIsNone(soil_source_for_audit({"source": None}))
        self.assertIsNone(soil_source_for_audit("Unavailable"))

    def test_generated_markdown_is_not_shown_raw(self):
        answer = "### **Rice advice**\n- Check `water` level.\n- See https://example.org/rice_guide"
        self.assertEqual(
            to_telegram_plain_text(answer),
            "Rice advice\n• Check water level.\n• See https://example.org/rice_guide",
        )

    def test_legacy_unsourced_seeder_cannot_run(self):
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            legacy_ingest()


if __name__ == "__main__":
    unittest.main()
