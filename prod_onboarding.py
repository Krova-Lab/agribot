"""Persistence and localized copy for the future public bot onboarding."""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from typing import Any

from config.prod_database import get_prod_db_params

SUPPORTED_LANGUAGES = ("km", "en", "fr")
DEFAULT_LANGUAGE = "km"


@dataclass(frozen=True)
class ProductionUser:
    telegram_id: int
    status: str
    preferred_language: str
    location_text: str | None
    location_lat: float | None
    location_lon: float | None
    onboarding_step: str
    waitlist_position: int | None = None


def infer_language(telegram_language: str | None) -> str:
    """Map Telegram's language hint to a supported UI language."""

    value = (telegram_language or "").lower().split("-")[0].split("_")[0]
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def _text(lang: str, key: str, **values: Any) -> str:
    language = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    message = COPY[language][key]
    return message.format(**values)


def welcome_message(lang: str, position: int | None) -> str:
    position_text = str(position) if position is not None else "—"
    return _text(lang, "welcome", position=position_text)


def settings_message(user: ProductionUser) -> str:
    lang = user.preferred_language
    location = user.location_text or _text(lang, "not_set")
    if user.location_lat is not None and user.location_lon is not None:
        location = f"{user.location_lat:.4f}, {user.location_lon:.4f}"
    return _text(lang, "settings", language=lang.upper(), location=html.escape(location))


def waitlist_message(user: ProductionUser) -> str:
    position = str(user.waitlist_position) if user.waitlist_position else "—"
    return _text(user.preferred_language, "waitlist", position=position)


COPY = {
    "km": {
        "welcome": (
            "🌾 <b>សូមស្វាគមន៍មកកាន់ Krova Agri</b>\n\n"
            "ជំនួយការព័ត៌មានកសិកម្មសម្រាប់កម្ពុជា។ អ្នកអាចសួរជាភាសាខ្មែរ អង់គ្លេស ឬបារាំង "
            "តាមអត្ថបទ សំឡេង ឬរូបថត។\n\n"
            "✅ អ្នកត្រូវបានចុះឈ្មោះក្នុងបញ្ជីរង់ចាំរួចហើយ។\n"
            "លេខរៀងបច្ចុប្បន្ន៖ <b>{position}</b>\n\n"
            "ការកំណត់ភាសា និងទីតាំងគឺជាជម្រើស។ វាជួយឱ្យចម្លើយសមស្របជាងមុន ប៉ុន្តែអ្នកអាចរំលងបាន។"
        ),
        "waitlist": "🕓 អ្នកស្ថិតក្នុងបញ្ជីរង់ចាំ។\nលេខរៀងបច្ចុប្បន្ន៖ <b>{position}</b>",
        "settings": "⚙️ <b>ការកំណត់</b>\nភាសា៖ {language}\nទីតាំង៖ {location}",
        "not_set": "មិនទាន់កំណត់",
        "language_prompt": "🌐 ជ្រើសរើសភាសាដែលអ្នកចង់ប្រើ៖",
        "location_prompt": "📍 បញ្ចូលខេត្ត ឬស្រុករបស់អ្នក (ជាជម្រើស)។ អ្នកអាចចុចរំលងបាន។",
        "location_saved": "✅ បានរក្សាទុកទីតាំងរបស់អ្នក។",
        "done": "បានហើយ។ អ្នកអាចប្រើ /settings ដើម្បីកែប្រែការកំណត់នៅពេលក្រោយ។",
        "quota": "📊 អ្នកនៅក្នុងបញ្ជីរង់ចាំ។ កូតានឹងបង្ហាញនៅពេលការចូលប្រើត្រូវបានបើក។",
    },
    "en": {
        "welcome": (
            "🌾 <b>Welcome to Krova Agri</b>\n\n"
            "Agricultural information for Cambodia. Ask in Khmer, English, or French "
            "by text, voice message, or photo.\n\n"
            "✅ You are now on the wait-list.\n"
            "Current position: <b>{position}</b>\n\n"
            "Language and location are optional. They can make answers more relevant, but you can skip them."
        ),
        "waitlist": "🕓 You are on the wait-list.\nCurrent position: <b>{position}</b>",
        "settings": "⚙️ <b>Settings</b>\nLanguage: {language}\nLocation: {location}",
        "not_set": "Not set",
        "language_prompt": "🌐 Choose your preferred language:",
        "location_prompt": "📍 Send your province or district (optional). You can skip this step.",
        "location_saved": "✅ Your location has been saved.",
        "done": "All set. Use /settings any time to update your preferences.",
        "quota": "📊 You are on the wait-list. Your quota will appear when access is enabled.",
    },
    "fr": {
        "welcome": (
            "🌾 <b>Bienvenue sur Krova Agri</b>\n\n"
            "Des informations agricoles pour le Cambodge. Posez vos questions en khmer, en anglais "
            "ou en français, par texte, message vocal ou photo.\n\n"
            "✅ Vous êtes inscrit sur la liste d'attente.\n"
            "Position actuelle : <b>{position}</b>\n\n"
            "La langue et la localisation sont facultatives. Elles peuvent affiner les réponses, mais vous pouvez passer cette étape."
        ),
        "waitlist": "🕓 Vous êtes sur la liste d'attente.\nPosition actuelle : <b>{position}</b>",
        "settings": "⚙️ <b>Paramètres</b>\nLangue : {language}\nLocalisation : {location}",
        "not_set": "Non définie",
        "language_prompt": "🌐 Choisissez votre langue préférée :",
        "location_prompt": "📍 Indiquez votre province ou votre district (facultatif). Vous pouvez passer cette étape.",
        "location_saved": "✅ Votre localisation a été enregistrée.",
        "done": "C'est noté. Utilisez /settings pour modifier vos préférences à tout moment.",
        "quota": "📊 Vous êtes sur la liste d'attente. Votre quota apparaîtra lorsque l'accès sera ouvert.",
    },
}


class ProductionUserStore:
    """Small database boundary kept independent from the pilot bot access code."""

    def __init__(self, connection_factory=None):
        if connection_factory is not None:
            self.connection_factory = connection_factory
            return
        self.connection_factory = self._default_connection

    @staticmethod
    def _default_connection():
        import psycopg2

        return psycopg2.connect(**get_prod_db_params())

    def _connect(self):
        return self.connection_factory()

    def enroll(self, telegram_id: int, username: str | None, first_name: str | None,
               language: str, referral_code: str | None = None) -> ProductionUser:
        language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO prod_bot_users
                    (telegram_id, username, first_name, preferred_language, referral_code, updated_at)
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, prod_bot_users.username),
                    first_name = COALESCE(EXCLUDED.first_name, prod_bot_users.first_name),
                    updated_at = now()
                """,
                (telegram_id, username, first_name, language, referral_code),
            )
            cur.execute(
                """
                SELECT u.telegram_id, u.status, u.preferred_language, u.location_text,
                       u.location_lat, u.location_lon, u.onboarding_step,
                       (SELECT COUNT(*) + 1 FROM prod_bot_users ahead
                        WHERE ahead.status = 'waitlist' AND ahead.created_at < u.created_at)
                FROM prod_bot_users u WHERE u.telegram_id = %s
                """,
                (telegram_id,),
            )
            return self._row_to_user(cur.fetchone())

    def get(self, telegram_id: int) -> ProductionUser | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT telegram_id, status, preferred_language, location_text,
                          location_lat, location_lon, onboarding_step,
                          (SELECT COUNT(*) + 1 FROM prod_bot_users ahead
                           WHERE ahead.status = 'waitlist' AND ahead.created_at < u.created_at)
                   FROM prod_bot_users u WHERE telegram_id = %s""",
                (telegram_id,),
            )
            row = cur.fetchone()
            return self._row_to_user(row) if row else None

    def set_language(self, telegram_id: int, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError("Unsupported language")
        self._execute("UPDATE prod_bot_users SET preferred_language = %s, onboarding_step = 'complete', updated_at = now() WHERE telegram_id = %s", (language, telegram_id))

    def set_location_text(self, telegram_id: int, location: str) -> None:
        self._execute("UPDATE prod_bot_users SET location_text = %s, location_lat = NULL, location_lon = NULL, onboarding_step = 'complete', updated_at = now() WHERE telegram_id = %s", (location[:255], telegram_id))

    def set_location_coordinates(self, telegram_id: int, latitude: float, longitude: float) -> None:
        self._execute("UPDATE prod_bot_users SET location_text = NULL, location_lat = %s, location_lon = %s, onboarding_step = 'complete', updated_at = now() WHERE telegram_id = %s", (round(latitude, 6), round(longitude, 6), telegram_id))

    def set_step(self, telegram_id: int, step: str) -> None:
        if step not in ("complete", "awaiting_language", "awaiting_location"):
            raise ValueError("Unsupported onboarding step")
        self._execute("UPDATE prod_bot_users SET onboarding_step = %s, updated_at = now() WHERE telegram_id = %s", (step, telegram_id))

    def _execute(self, query: str, params: tuple) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, params)

    @staticmethod
    def _row_to_user(row) -> ProductionUser:
        return ProductionUser(*row)
