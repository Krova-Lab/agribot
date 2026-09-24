"""Web grounding tests with provider and database access fully mocked."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

import web_research  # noqa: E402


class WebResearchTests(unittest.TestCase):
    def test_grounding_sources_and_search_queries_are_returned_for_audit(self):
        metadata = SimpleNamespace(
            web_search_queries=["Cambodia rice irrigation guidance IRRI"],
            grounding_chunks=[
                SimpleNamespace(web=SimpleNamespace(title="IRRI", uri="https://irri.org/water")),
                SimpleNamespace(web=SimpleNamespace(title="IRRI duplicate", uri="https://irri.org/water")),
            ],
            grounding_supports=[
                SimpleNamespace(
                    segment=SimpleNamespace(text="Water levels vary by crop stage."),
                    grounding_chunk_indices=[0],
                ),
            ],
        )
        response = SimpleNamespace(
            candidates=[SimpleNamespace(grounding_metadata=metadata)],
            text="IRRI recommends managing water according to crop stage.",
        )
        model = SimpleNamespace(generate_content=MagicMock(return_value=response))
        client = SimpleNamespace(models=model)

        with patch.dict(os.environ, {"KROVA_WEB_RESEARCH_ENABLED": "true", "GEMINI_API_KEY": "test-key"}):
            with patch.object(web_research, "_client", return_value=client):
                result = web_research.research_web("How should I irrigate rice in Cambodia?", "en")

        self.assertEqual(result.status, "grounded")
        self.assertEqual(result.search_queries, ("Cambodia rice irrigation guidance IRRI",))
        self.assertEqual(len(result.sources), 1)
        self.assertIn("https://irri.org/water", result.prompt_context())
        self.assertIn("Water levels vary by crop stage", result.prompt_context())
        self.assertIn("claim_sources", result.trace())
        config = model.generate_content.call_args.kwargs["config"]
        self.assertTrue(config.tools)

    def test_missing_grounding_metadata_is_not_reported_as_a_search(self):
        response = SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=None)], text="Answer without search")
        client = SimpleNamespace(models=SimpleNamespace(generate_content=MagicMock(return_value=response)))

        with patch.dict(os.environ, {"KROVA_WEB_RESEARCH_ENABLED": "true", "GEMINI_API_KEY": "test-key"}):
            with patch.object(web_research, "_client", return_value=client):
                result = web_research.research_web("Rice irrigation in Cambodia", "en")

        self.assertEqual(result.status, "not_grounded")
        self.assertEqual(result.sources, ())

    def test_greetings_skip_web_search(self):
        with patch.object(web_research, "_client") as client:
            result = web_research.research_web("bonjour", "fr")
        self.assertEqual(result.status, "skipped")
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
