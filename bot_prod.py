"""Future public Telegram bot: wait-list onboarding and user settings only."""

from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from prod_onboarding import (
    COPY,
    ProductionUserStore,
    infer_language,
    settings_message,
    welcome_message,
    waitlist_message,
)

load_dotenv()
logger = logging.getLogger(__name__)
TELEGRAM_TOKEN = os.getenv("KROVA_PROD_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_PROD_BOT_TOKEN")
STORE = ProductionUserStore()


def _user(update: Update):
    return update.effective_user


def _private_chat(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.type == "private")


def onboarding_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Language / ភាសា / Langue", callback_data="prod:language")],
        [InlineKeyboardButton("📍 Location (optional)", callback_data="prod:location")],
        [InlineKeyboardButton("✅ Done", callback_data="prod:done")],
    ])


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇰🇭 ខ្មែរ", callback_data="prod:lang:km"),
        InlineKeyboardButton("🇬🇧 English", callback_data="prod:lang:en"),
        InlineKeyboardButton("🇫🇷 Français", callback_data="prod:lang:fr"),
    ]])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Language / ភាសា / Langue", callback_data="prod:language")],
        [InlineKeyboardButton("📍 Update location", callback_data="prod:location")],
        [InlineKeyboardButton("✅ Done", callback_data="prod:done")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _private_chat(update) or not update.message:
        return
    user = _user(update)
    referral = context.args[0][:64] if context.args else None
    record = STORE.enroll(user.id, user.username, user.first_name, infer_language(user.language_code), referral)
    await update.message.reply_text(
        welcome_message(record.preferred_language, record.waitlist_position),
        reply_markup=onboarding_keyboard(record.preferred_language),
        parse_mode="HTML",
    )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _private_chat(update) or not update.message:
        return
    user = _user(update)
    record = STORE.get(user.id)
    if not record:
        await start(update, context)
        return
    await update.message.reply_text(settings_message(record), reply_markup=settings_keyboard(), parse_mode="HTML")


async def quota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _private_chat(update) or not update.message:
        return
    record = STORE.get(_user(update).id)
    if not record:
        await start(update, context)
        return
    await update.message.reply_text(COPY[record.preferred_language]["quota"], parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "🌾 Krova Agri\n\n"
        "/start — Join the wait-list\n"
        "/settings — Language and optional location\n"
        "/quota — Access and usage status\n"
        "/help — Show this help",
    )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return
    await query.answer()
    record = STORE.get(query.from_user.id)
    if not record:
        return
    action = query.data or ""
    if action == "prod:language":
        await query.edit_message_text(COPY[record.preferred_language]["language_prompt"], reply_markup=language_keyboard(), parse_mode="HTML")
    elif action.startswith("prod:lang:"):
        language = action.rsplit(":", 1)[-1]
        STORE.set_language(record.telegram_id, language)
        updated = STORE.get(record.telegram_id)
        await query.edit_message_text(COPY[language]["done"] + "\n\n" + settings_message(updated), reply_markup=settings_keyboard(), parse_mode="HTML")
    elif action == "prod:location":
        STORE.set_step(record.telegram_id, "awaiting_location")
        await query.edit_message_text(COPY[record.preferred_language]["location_prompt"], parse_mode="HTML")
    elif action == "prod:done":
        STORE.set_step(record.telegram_id, "complete")
        await query.edit_message_text(COPY[record.preferred_language]["done"], parse_mode="HTML")


async def location_or_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _private_chat(update) or not update.message:
        return
    record = STORE.get(_user(update).id)
    if not record or record.onboarding_step != "awaiting_location":
        return
    if update.message.location:
        STORE.set_location_coordinates(record.telegram_id, update.message.location.latitude, update.message.location.longitude)
    elif update.message.text and update.message.text.strip().lower() not in ("/skip", "skip"):
        STORE.set_location_text(record.telegram_id, update.message.text.strip())
    else:
        STORE.set_step(record.telegram_id, "complete")
    updated = STORE.get(record.telegram_id)
    await update.message.reply_text(COPY[record.preferred_language]["location_saved"] + "\n\n" + settings_message(updated), parse_mode="HTML")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled production bot exception: %s", context.error, exc_info=context.error)


async def post_init(application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Join the wait-list"),
        BotCommand("settings", "Language and optional location"),
        BotCommand("quota", "Access and usage status"),
        BotCommand("help", "How to use Krova Agri"),
    ])


def build_application():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("KROVA_PROD_TELEGRAM_BOT_TOKEN is required to start the production bot")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("quota", quota))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(callback, pattern=r"^prod:"))
    application.add_handler(MessageHandler(filters.TEXT | filters.LOCATION, location_or_text))
    application.add_error_handler(error_handler)
    return application


if __name__ == "__main__":
    build_application().run_polling(drop_pending_updates=True)
