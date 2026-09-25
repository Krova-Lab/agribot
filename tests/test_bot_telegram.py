"""End-to-end handler regression tests using Telegram and service doubles."""

import os
import sys
import types
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

try:
    import bot_telegram  # noqa: E402
except ModuleNotFoundError as exc:  # Keep the dependency-light suite usable locally.
    if exc.name != "telegram":
        raise
    # The handler test only needs Telegram value objects; the CI job installs
    # python-telegram-bot and therefore uses the real package.
    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardButton = lambda *args, **kwargs: (args, kwargs)
    telegram.InlineKeyboardMarkup = lambda *args, **kwargs: (args, kwargs)
    telegram.BotCommand = lambda *args, **kwargs: (args, kwargs)
    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.ApplicationBuilder = object
    telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
    telegram_ext.CommandHandler = object
    telegram_ext.MessageHandler = object
    telegram_ext.CallbackQueryHandler = object
    telegram_ext.filters = types.SimpleNamespace(TEXT=object(), COMMAND=object(), PHOTO=object(), VOICE=object(), LOCATION=object())
    sys.modules["telegram"] = telegram
    sys.modules["telegram.ext"] = telegram_ext
    import bot_telegram  # noqa: E402


class BotMessagePathTests(unittest.IsolatedAsyncioTestCase):
    def test_source_request_detection_is_explicit(self):
        self.assertFalse(bot_telegram.user_requests_sources("Comment traiter les feuilles jaunes du riz ?"))
        self.assertTrue(bot_telegram.user_requests_sources("Peux-tu me donner les sources ?"))

    async def test_text_without_location_reaches_rag_model_and_telegram(self):
        user = SimpleNamespace(id=12345, username="farmer")
        message = SimpleNamespace(
            text="Comment traiter les feuilles jaunes du riz ?",
            caption=None,
            photo=None,
            voice=None,
            reply_text=AsyncMock(),
        )
        update = SimpleNamespace(effective_user=user, message=message)

        progress = SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())
        message.reply_text.return_value = progress
        audit_cursor = MagicMock()
        audit_cursor.fetchall.return_value = []
        audit_cursor.fetchone.return_value = (77,)
        audit_connection = MagicMock()
        audit_connection.cursor.return_value = audit_cursor

        with patch.object(bot_telegram.access_control, "is_allowed_access", return_value=True), \
             patch.object(bot_telegram.access_control, "check_user_rate_limit", return_value=(True, "", 0, 30)), \
             patch.object(bot_telegram.access_control, "get_user_role", return_value="tester"), \
             patch.object(bot_telegram, "build_location_context", return_value=(
                 None,
                 None,
                 "No plot-specific soil lookup; Cambodia-wide agronomic context",
                 "No plot-specific weather lookup; Cambodia-wide seasonal context",
                 "Cambodia-wide baseline; no specific location confirmed",
             )) as location, \
             patch.object(bot_telegram, "retrieve_rag", return_value=SimpleNamespace(
                 status="ok",
                 sources=(SimpleNamespace(
                     title="IRRI rice guide", content="Yellow leaves guidance", url="https://irri.org/rice",
                     publisher="IRRI", publication_date=None, license="CC BY", source_locator="Chapter 2, p. 8", distance=0.1,
                     trace=lambda rank: {"document_id": 1, "rank": rank, "url": "https://irri.org/rice"},
                 ),),
                 trace=lambda: {"status": "ok", "sources": [{"document_id": 1, "url": "https://irri.org/rice"}]},
             )) as rag, \
             patch.object(bot_telegram, "format_rag_context", return_value="[RAG SOURCE 1] IRRI rice guide"), \
             patch.object(bot_telegram, "research_web", return_value=SimpleNamespace(
                 prompt_context=lambda: "Google Search found a Cambodia-relevant source",
                 trace=lambda: {"status": "grounded", "sources": [{"title": "IRRI", "url": "https://irri.org/water"}]},
                 status="grounded", sources=[SimpleNamespace(title="IRRI", url="https://irri.org/water")],
             )) as web_research, \
             patch.object(bot_telegram, "ask_llm", return_value=("Réponse générale pour le Cambodge", "gemini:test")) as llm, \
             patch.object(bot_telegram, "InlineKeyboardButton", return_value=object()), \
             patch.object(bot_telegram, "InlineKeyboardMarkup", return_value=object()), \
             patch.object(bot_telegram.psycopg2, "connect", return_value=audit_connection):
            bot_telegram.USER_LOCATIONS.pop(user.id, None)
            await bot_telegram.handle_user_input(update, SimpleNamespace())

        location.assert_called_once()
        self.assertIsNone(location.call_args.args[0])
        rag.assert_called_once_with(message.text, limit=3)
        web_research.assert_called_once_with(message.text, "fr")
        llm.assert_called_once()
        prompt = llm.call_args.args[0]
        self.assertIn("Cambodia-wide baseline; no specific location confirmed", prompt)
        self.assertIn("[RAG SOURCE 1] IRRI rice guide", prompt)
        self.assertIn("Preserve exact values from cited passages", prompt)
        self.assertIn("Never average, widen, narrow, or silently merge conflicting values", prompt)
        self.assertIn("Treat publication date as evidence quality, not decoration", prompt)
        self.assertIn("Google Search found a Cambodia-relevant source", prompt)
        self.assertIn("Missing GPS or a missing province must never block", prompt)
        self.assertIn("provide that Cambodia-wide baseline directly", prompt)
        self.assertEqual(message.reply_text.await_count, 2)
        self.assertIn("Réponse générale pour le Cambodge", message.reply_text.await_args.args[0])
        self.assertNotIn("https://irri.org/rice", message.reply_text.await_args.args[0])
        self.assertNotIn("IRRI rice guide (Chapter 2, p. 8)", message.reply_text.await_args.args[0])
        self.assertNotIn("https://irri.org/water", message.reply_text.await_args.args[0])
        audit_values = audit_cursor.execute.call_args.args[1]
        trace = json.loads(audit_values[-1])
        self.assertEqual(trace["rag"]["status"], "ok")
        self.assertEqual(trace["web"]["status"], "grounded")
        self.assertIn("https://irri.org/water", trace["web"]["sources"][0]["url"])
        progress.delete.assert_awaited_once()
        self.assertNotIn(user.id, bot_telegram.USER_LOCATIONS)


if __name__ == "__main__":
    unittest.main()
