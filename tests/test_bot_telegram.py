"""End-to-end handler regression tests using Telegram and service doubles."""

import os
import sys
import types
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
                 "Unavailable: no coordinates supplied",
                 "Unavailable: no coordinates supplied",
                 "Cambodia; no specific location confirmed",
             )) as location, \
             patch.object(bot_telegram, "search_rag", return_value="[rice] Yellow leaves guidance") as rag, \
             patch.object(bot_telegram, "ask_llm", return_value=("Réponse générale pour le Cambodge", "gemini:test")) as llm, \
             patch.object(bot_telegram.psycopg2, "connect", return_value=audit_connection):
            bot_telegram.USER_LOCATIONS.pop(user.id, None)
            await bot_telegram.handle_user_input(update, SimpleNamespace())

        location.assert_called_once()
        self.assertIsNone(location.call_args.args[0])
        rag.assert_called_once_with(message.text, limit=2)
        llm.assert_called_once()
        prompt = llm.call_args.args[0]
        self.assertIn("Cambodia; no specific location confirmed", prompt)
        self.assertIn("[rice] Yellow leaves guidance", prompt)
        self.assertIn("best useful general guidance for Cambodia first", prompt)
        self.assertEqual(message.reply_text.await_count, 2)
        self.assertIn("Réponse générale pour le Cambodge", message.reply_text.await_args.args[0])
        progress.delete.assert_awaited_once()
        self.assertNotIn(user.id, bot_telegram.USER_LOCATIONS)


if __name__ == "__main__":
    unittest.main()
