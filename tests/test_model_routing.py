"""Offline checks for per-task routing and media interpretation."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

import llm_adapter  # noqa: E402
import media_pipeline  # noqa: E402


class ModelRoutingTests(unittest.TestCase):
    def test_routes_are_ordered_and_deduplicated(self):
        with patch.dict(os.environ, {"KROVA_RESPONSE_MODELS": "azure:gpt-4o, gemini:flash, azure:gpt-4o"}):
            self.assertEqual(
                [route.label for route in llm_adapter.configured_routes("response")],
                ["azure:gpt-4o", "gemini:flash"],
            )

    def test_failover_uses_second_provider(self):
        with patch.dict(os.environ, {"KROVA_RESPONSE_MODELS": "gemini:flash,azure:gpt-4o"}):
            with patch.object(llm_adapter, "_gemini_generate", side_effect=TimeoutError):
                with patch.object(llm_adapter, "_azure_generate", return_value="Khmer answer") as azure:
                    answer, model = llm_adapter.ask_llm("Question")
        self.assertEqual((answer, model), ("Khmer answer", "azure:gpt-4o"))
        azure.assert_called_once()

    def test_azure_chat_receives_image_only_for_vision(self):
        with patch.dict(os.environ, {
            "AZURE_FOUNDRY_BASE_URL": "https://example.openai.azure.com/openai/v1",
            "AZURE_FOUNDRY_API_KEY": "test-key",
        }):
            with patch.object(llm_adapter.requests, "post") as post:
                post.return_value.json.return_value = {"choices": [{"message": {"content": "Rice leaf"}}]}
                answer = llm_adapter._azure_generate(
                    llm_adapter.ModelRoute("azure", "gpt-4o"), "Describe", b"image", "image/jpeg", 0, "vision"
                )
        self.assertEqual(answer, "Rice leaf")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gpt-4o")
        self.assertTrue(payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_text_path_does_not_interpret_media(self):
        with patch.object(media_pipeline, "ask_llm") as ask:
            prepared = media_pipeline.prepare_input("rice leaves", None, "image/jpeg")
        self.assertEqual(prepared.retrieval_query, "rice leaves")
        ask.assert_not_called()

    def test_voice_transcript_becomes_retrieval_query(self):
        with patch.object(media_pipeline, "ask_llm", return_value=("ស្រូវនៅកំពត", "gemini:flash")) as ask:
            prepared = media_pipeline.prepare_input("", b"ogg", "audio/ogg")
        self.assertEqual(prepared.user_text, "ស្រូវនៅកំពត")
        self.assertEqual(prepared.retrieval_query, "ស្រូវនៅកំពត")
        self.assertEqual(ask.call_args.kwargs["task"], "transcription")

    def test_unintelligible_voice_is_not_sent_to_retrieval(self):
        with patch.object(media_pipeline, "ask_llm", return_value=("[NO_SPEECH]", "gemini:flash")):
            with self.assertRaises(media_pipeline.InputInterpretationError):
                media_pipeline.prepare_input("", b"ogg", "audio/ogg")

    def test_photo_observation_does_not_replace_users_language(self):
        with patch.object(media_pipeline, "ask_llm", return_value=("yellow rice leaves", "azure:gpt-4o")):
            prepared = media_pipeline.prepare_input("", b"jpg", "image/jpeg")
        self.assertEqual(prepared.user_text, "")
        self.assertIn("yellow rice leaves", prepared.retrieval_query)


if __name__ == "__main__":
    unittest.main()
