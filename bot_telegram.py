USER_LOCATIONS = {}
import access_control
# TODO: REOPEN PUBLIC ACCESS FOR THE PILOT PHASE / GENERAL DEPLOYMENT

import os
import io
import re
import time
import asyncio
import logging
import psycopg2
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand

async def post_init(application):
    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("quota", "Check limits"),
        BotCommand("lang", "Change language")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("BotCommand menu configured successfully.")
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from dotenv import load_dotenv

from llm_adapter import ask_llm
from config.prompt_loader import load_prompts
from config.database import get_db_params
from api_clients import get_soil_data_with_fallback, identify_plant_plantnet
from agent_workflow import get_weather_history
from rag_search import search_rag
from telegram_format import to_telegram_plain_text
from location_context import build_location_context, soil_source_for_audit

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PARAMS = get_db_params()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_CACHE_DIR = os.path.join(BASE_DIR, "image_cache")
AUDIO_CACHE_DIR = os.path.join(BASE_DIR, "audio_cache")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class RedactSecretsFilter(logging.Filter):
    """Filter to redact TELEGRAM_TOKEN and GEMINI_API_KEY secrets from log records."""
    def __init__(self, name=""):
        super().__init__(name)
        self.secret_keys = ["TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY", "GOOGLE_API_KEY", "TELEGRAM_ADMIN_BOT_TOKEN"]

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = [os.getenv(k) for k in self.secret_keys if os.getenv(k)]

        def redact(text: str) -> str:
            for secret in secrets:
                if secret and secret in text:
                    text = text.replace(secret, "[REDACTED_SECRET]")
            text = re.sub(r"file/bot[0-9]{8,10}:[a-zA-Z0-9_-]{35}", "file/bot[REDACTED_SECRET]", text)
            text = re.sub(r"/bot[0-9]{8,10}:[a-zA-Z0-9_-]{35}/", "/bot[REDACTED_SECRET]/", text)
            text = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot[REDACTED_SECRET]", text)
            return text

        if record.msg is not None:
            record.msg = redact(str(record.msg))

        if record.args:
            def redact_arg(arg):
                if arg is None or isinstance(arg, (int, float, bool)):
                    return arg
                text = str(arg)
                for secret in secrets:
                    if secret and secret in text:
                        text = text.replace(secret, "[REDACTED_SECRET]")
                text = re.sub(r"file/bot[0-9]{8,10}:[a-zA-Z0-9_-]{35}", "file/bot[REDACTED_SECRET]", text)
                text = re.sub(r"/bot[0-9]{8,10}:[a-zA-Z0-9_-]{35}/", "/bot[REDACTED_SECRET]/", text)
                text = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot[REDACTED_SECRET]", text)
                return text

            if isinstance(record.args, tuple):
                record.args = tuple(redact_arg(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: redact_arg(v) for k, v in record.args.items()}

        return True

redact_filter = RedactSecretsFilter()
logging.getLogger().addFilter(redact_filter)
for h in logging.getLogger().handlers:
    h.addFilter(redact_filter)

logger = logging.getLogger(__name__)
PROMPTS = load_prompts()

def detect_ui_lang(text: str) -> str:
    if not text:
        return "kh"
    # Khmer alphabet detected
    if re.search(r"[\u1780-\u17FF]", text):
        return "kh"

    lower_t = text.lower().strip()

    # French-specific markers
    has_fr_accents = bool(re.search(r"[éèêëàâîïôùûç]", lower_t))
    fr_stop_words = {"le", "la", "les", "des", "du", "un", "une", "dans", "sur", "pour", "avec", "est", "c'est", "que", "qui"}
    fr_keywords = {"bonjour", "salut", "comment", "pourquoi", "maladie", "feuille", "riz", "culture", "engrais", "parasite"}

    words = set(re.findall(r"\b\w+\b", lower_t))
    if has_fr_accents or words.intersection(fr_keywords) or words.intersection(fr_stop_words):
        return "fr"

    # Latin alphabet without French-specific markers -> English
    if re.search(r"[a-zA-Z]", text):
        return "en"

    return "kh"

BUTTON_TEXTS = {
    "kh": {"pos": "👍 ត្រឹមត្រូវ", "neg": "👎 មិនត្រឹមត្រូវ"},
    "fr": {"pos": "👍 Utile", "neg": "👎 À revoir"},
    "en": {"pos": "👍 Useful", "neg": "👎 Inaccurate"}
}

FEEDBACK_MSGS = {
    "kh": {
        "pos": "🙏 អរគុណសម្រាប់ការផ្ដល់មតិកែលម្អ!",
        "neg": "🙏 សូមអរគុណ យើងខ្ញុំនឹងកែលម្អចំណុចនេះ।"
    },
    "fr": {
        "pos": "🙏 Merci pour votre retour !",
        "neg": "🙏 Merci, nous prenons note pour améliorer la réponse."
    },
    "en": {
        "pos": "🙏 Thank you for your feedback!",
        "neg": "🙏 Thank you, we will improve this response."
    }
}

def get_pilot_full_message() -> str:
    max_users = access_control.get_max_pilot_users()
    return (
        "⛔ <b>សូមអភ័យទោស / Accès restreint</b>\n\n"
        f"ក្រុមតេស្តសាកល្បងដំណាក់កាលទី១ (Pilot Test) ចំនួន {max_users} កន្លែង បានពេញហើយ។ "
        "សូមអរគុណចំពោះការចាប់អារម្មណ៍របស់អ្នក!\n\n"
        f"La cohorte de test pilote de {max_users} places est actuellement complète. "
        "Merci pour votre intérêt !"
    )

PILOT_FULL_MESSAGE = get_pilot_full_message()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id if user else 0
    username = user.username if user else None
    if not access_control.is_allowed_access(telegram_id, username=username):
        await update.message.reply_text(get_pilot_full_message(), parse_mode="HTML")
        return

    welcome_text = (
        "🌾 <b>សួស្តី! ស្វាគមន៍មកកាន់ Krova Agri</b>\n"
        "🧪 <b>ស្ថានភាព៖ <i>វគ្គតេស្តសាកល្បង (Pilot Test Phase)</i></b>\n\n"
        "ជំនួយការកសិកម្មឆ្លាតវៃសម្រាប់កសិករនៅកម្ពុជា។\n\n"
        "<b>សមត្ថភាពចម្បង៖</b>\n"
        "1️⃣ <b>ការវិភាគជំងឺដំណាំតាមរូបថត</b>\n"
        "   - ថតរូបស្លឹក ឬដំណាំដែលមានបញ្ហាដើម្បីទទួលបានការវិភាគភ្លាមៗ។\n"
        "2️⃣ <b>សួរសំណួរជាសំឡេង</b>\n"
        "   - អាចផ្ញើសារសំឡេងជាភាសាខ្មែរ អង់គ្លេស ឬបារាំង ដើម្បីសួរសំណួរ។\n"
        "3️⃣ <b>ព្យាករណ៍អាកាសធាតុ និងការណែនាំតាមតំបន់</b>\n"
        "   - ចែករំលែកទីតាំង (Location) របស់អ្នក (ជាជម្រើស) ដើម្បីទទួលបានព័ត៌មានអាកាសធាតុ និងដីជាក់ស្តែង។\n\n"
        "<b>បញ្ជាប្រើប្រាស់ / Commands:</b>\n"
        "• /quota : មើលចំនួនប្រើប្រាស់ប្រចាំថ្ងៃ (Check daily limits)\n"
        "• /lang : ផ្លាស់ប្តូរភាសា (Change language)\n\n"
        "────────────────────────\n"
        "🌾 <b>Welcome to Krova Agri</b>\n"
        "🧪 Status: <b>Pilot Test Phase</b>\n\n"
        "Agricultural information for people farming in Cambodia.\n\n"
        "<b>Key Features:</b>\n"
        "• <b>Crop Photo Review:</b> Send a plant photo for an initial assessment, not a definitive diagnosis.\n"
        "• <b>Voice Questions:</b> Ask questions via voice note in Khmer, English, or French.\n"
        "• <b>Local Weather & Soil Insights:</b> Tell me your province for general context. GPS sharing is optional for plot-specific data.\n\n"
        "────────────────────────\n"
        "<i>(FR: Bienvenue sur Krova Agri, votre assistant agronomique en phase de test pilote.)</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id if user else 0
    username = user.username if user else None

    if not access_control.is_allowed_access(telegram_id, username=username):
        await update.message.reply_text(get_pilot_full_message(), parse_mode="HTML")
        return

    daily_count = access_control.get_user_daily_count(telegram_id)
    max_daily = 30
    remaining = max(0, max_daily - daily_count)

    quota_msg = (
        "📊 <b>កម្រិតប្រើប្រាស់ / Usage & Quota</b>\n\n"
        f"• <b>សំណើបានប្រើប្រាស់ថ្ងៃនេះ / Requests used today:</b> {daily_count}\n"
        f"• <b>កម្រិតអនុញ្ញាតប្រចាំថ្ងៃ / Daily limit:</b> {max_daily} requests/day\n"
        f"• <b>ចំនួននៅសល់ថ្ងៃនេះ / Remaining requests:</b> {remaining}\n\n"
        "<i>(កម្រិតនេះកំណត់ដើម្បីការពារប្រព័ន្ធ anti-flood / Limit set to prevent abuse and flood)</i>"
    )
    await update.message.reply_text(quota_msg, parse_mode="HTML")

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id if user else 0
    if not access_control.is_allowed_access(telegram_id):
        await update.message.reply_text(get_pilot_full_message(), parse_mode="HTML")
        return

    keyboard = [
        [
            InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ (Khmer)", callback_data="set_lang_km"),
            InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"),
            InlineKeyboardButton("🇫🇷 Français", callback_data="set_lang_fr")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "🌐 <b>ជ្រើសរើសភាសា / Choose your language / Choisissez votre langue :</b>\n\n"
        "សូមជ្រើសរើសភាសាដែលអ្នកចង់ប្រើប្រាស់ជាអាទិភាព។\n"
        "Please select your preferred language."
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="HTML")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user
    telegram_id = user.id if user else 0
    username = user.username if user else None

    if not access_control.is_allowed_access(telegram_id, username=username):
        await message.reply_text(get_pilot_full_message(), parse_mode="HTML")
        return

    loc = message.location
    if not loc:
        return

    lat, lon = round(loc.latitude, 4), round(loc.longitude, 4)
    USER_LOCATIONS[telegram_id] = (lat, lon)

    user_lang = access_control.get_user_language(telegram_id)
    confirm_msgs = {
        "km": f"📍 <b>ទទួលបានទីតាំងជោគជ័យ!</b>\nកូអរដោនេ: {lat}, {lon}\nប្រព័ន្ធនឹងប្រើប្រាស់ទិន្នន័យដី និងអាកាសធាតុសម្រាប់តំបន់នេះក្នុងការវិភាគបន្ទាប់។",
        "fr": f"📍 <b>Localisation enregistrée !</b>\nCoordonnées : {lat}, {lon}\nVos prochains diagnostics (sol & météo) seront calibrés pour cette parcelle.",
        "en": f"📍 <b>Location updated!</b>\nCoordinates: {lat}, {lon}\nNext soil and weather insights will be tailored to this plot."
    }
    await message.reply_text(confirm_msgs.get(user_lang, confirm_msgs["km"]), parse_mode="HTML")

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user
    telegram_id = user.id if user else 0
    username = user.username if user else None

    # 0. Early access control (token protection & pilot mode)
    if not access_control.is_allowed_access(telegram_id, username=username):
        await message.reply_text(get_pilot_full_message(), parse_mode="HTML")
        return

    # Strict anti-flood rate limiting (5 requests/minute & 30 requests/day)
    allowed, reason, daily_count, remaining = access_control.check_user_rate_limit(telegram_id, max_per_minute=5, max_per_day=30)
    if not allowed:
        if reason == "daily_limit":
            limit_msg = (
                "⏳ <b>អ្នកបានប្រើប្រាស់អស់កម្រិតកំណត់ប្រចាំថ្ងៃហើយ (30/30)។</b>\n"
                "សូមវិលត្រឡប់មកប្រើប្រាស់សារជាថ្មីនៅថ្ងៃស្អែក! អរគុណចំពោះការចូលរួម។\n\n"
                "─────────────\n"
                "⏳ <b>Daily limit reached (30/30 requests).</b>\n"
                "You have reached your daily question limit. Please come back tomorrow!"
            )
        else: # minute_limit
            limit_msg = (
                "⚠️ <b>សូមរង់ចាំបន្តិច!</b>\n"
                "អ្នកបានផ្ញើសំណើលឿនពេក (អតិបរមា ៥ ដងក្នុងមួយនាទី)។ សូមរង់ចាំមួយភ្លែត រួចព្យាយាមម្តងទៀត។\n\n"
                "─────────────\n"
                "⚠️ <b>Please wait a moment!</b>\n"
                "Too many requests sent too quickly (max 5 requests per minute). Please wait a few seconds."
            )
        await message.reply_text(limit_msg, parse_mode="HTML")
        return
    user_text = message.text or message.caption or ""
    has_photo = bool(message.photo)
    has_voice = bool(message.voice)

    lang = detect_ui_lang(user_text)
    WAIT_MSGS = {
        "kh": "⏳ កំពុងពិនិត្យទិន្នន័យ (Analyse RAG en cours)...",
        "fr": "⏳ Analyse agronomique RAG en cours...",
        "en": "⏳ Analyzing agronomic data (RAG in progress)..."
    }
    ERR_MSGS = {
        "kh": "⚠️ សូមអភ័យទោស ប្រព័ន្ធមានបញ្ហាបច្ចេកទេសបន្តិច។",
        "fr": "⚠️ Désolé, le système rencontre un problème technique momentané.",
        "en": "⚠️ Sorry, the system is experiencing a temporary technical issue."
    }

    # Waiting message adapted to voice or text input
    if has_voice:
        wait_text = "🎙️ កំពុងស្ដាប់ និងវិភាគសំឡេង (Écoute et analyse du vocal en cours)..."
    else:
        wait_text = WAIT_MSGS.get(lang, WAIT_MSGS["kh"])

    status_msg = await message.reply_text(wait_text)
    t_start = time.time()

    # 1. Download media (photo or voice) & Pl@ntNet
    media_bytes = None
    media_mime = "image/jpeg"
    media_file_id = None
    media_file_size = 0
    plantnet_info = ""

    if has_photo:
        photo_obj = message.photo[-1]
        media_file_id = photo_obj.file_id
        photo_file = await photo_obj.get_file()
        buf = io.BytesIO()
        await photo_file.download_to_memory(buf)
        media_bytes = buf.getvalue()
        media_file_size = len(media_bytes)
        media_mime = "image/jpeg"

        # Save to disk for auditability and debugging
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            safe_fname = f"{ts}_{telegram_id}_{photo_obj.file_unique_id}.jpg"
            img_save_path = os.path.join(IMAGE_CACHE_DIR, safe_fname)
            with open(img_save_path, "wb") as f:
                f.write(media_bytes)
            logger.info(f"Photo sauvegardée : {img_save_path} ({media_file_size} octets)")
        except Exception as e:
                logger.warning(f"Image disk-save error: {e}")

        # Process and optimise the image with PIL (Pillow)
        try:
            buf.seek(0)
            with Image.open(buf) as img:
                img = img.convert("RGB")
                if img.width > 1024 or img.height > 1024:
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                out_buf = io.BytesIO()
                img.save(out_buf, format="JPEG", quality=85)
                media_bytes = out_buf.getvalue()
        except Exception as e:
                logger.warning(f"PIL photo-processing error: {e}")

        try:
            plant_res = identify_plant_plantnet(media_bytes)
            if plant_res and "scientific_name" in plant_res:
                s_name = plant_res.get("scientific_name", "Inconnue")
                c_names = ", ".join(plant_res.get("common_names", []))
                score = plant_res.get("score", 0)
                plantnet_info = f"Pl@ntNet Identification: {s_name} ({c_names}) - Confidence: {score}%"
        except Exception as e:
                logger.warning(f"Pl@ntNet error: {e}")

    elif has_voice:
        voice_obj = message.voice
        media_file_id = voice_obj.file_id
        voice_file = await voice_obj.get_file()
        buf = io.BytesIO()
        await voice_file.download_to_memory(buf)
        media_bytes = buf.getvalue()
        media_file_size = len(media_bytes)
        media_mime = "audio/ogg"

        # Save to disk for auditability and debugging
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            safe_fname = f"{ts}_{telegram_id}_{voice_obj.file_unique_id}.ogg"
            voice_save_path = os.path.join(AUDIO_CACHE_DIR, safe_fname)
            with open(voice_save_path, "wb") as f:
                f.write(media_bytes)
            logger.info(f"Audio sauvegardé : {voice_save_path} ({media_file_size} octets)")
        except Exception as e:
                logger.warning(f"Audio disk-save error: {e}")

    # 2. Only request location-specific data when coordinates were explicitly shared.
    lat, lon, soil, weather, region_desc = build_location_context(
        USER_LOCATIONS.get(telegram_id), get_soil_data_with_fallback, get_weather_history
    )

    # 3. Dynamic semantic RAG through pgvector
    rag_start = time.time()
    rag_context = search_rag(user_text, limit=2) if user_text else ""
    if not rag_context:
        rag_context = PROMPTS["fallback_rag_context"]
    rag_ms = int((time.time() - rag_start) * 1000)

    # 4. Conversation history (enriched with the previous diagnosis/response)
    history_context = ""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("SELECT raw_user_text, diagnosis_title FROM interactions WHERE telegram_id = %s ORDER BY id DESC LIMIT 3;", (telegram_id,))
        rows = cur.fetchall()
        if rows:
            history_context = "\n".join([
                f"- Prior User: {r[0]}\n  Prior Advisor Response: {r[1]}"
                for r in reversed(rows)
            ])
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"SQL error: {e}")

    # 5. System prompt
    attached_desc = PROMPTS.get("attached_media", {}).get("none", "None")
    if has_photo:
        attached_desc = PROMPTS.get("attached_media", {}).get("image", attached_desc)
    elif has_voice:
        attached_desc = PROMPTS.get("attached_media", {}).get("audio", attached_desc)

    system_prompt = f"""
    {PROMPTS.get("system_prompt", "You are an agricultural assistant.")}

    Persona:
    {PROMPTS.get("persona", {})}

    Farmer Context:
    - Region: {region_desc}
    - Soil Baseline: {soil}
    - Recent Weather Context (Past 7 Days): {weather}
    - Botanical Identification (Pl@ntNet API): {plantnet_info if plantnet_info else "None (Visual only)"}
    - RAG Knowledge Base Retrieval:
    {rag_context}
    - Recent Messages: {history_context if history_context else "None"}
    - Attached Media: {attached_desc}
    - User Query: "{user_text if user_text else '[Voice Message]'}"

    Instructions:
    0. Source and location integrity:
       - Krova Agri is independent. Do not imply affiliation with CARDI, MAFF, or any other institution.
       - Do not attribute a recommendation to an institution from a document title alone. Name a source only when a specific, verifiable reference is available in the supplied context; otherwise say the source is unverified.
       - Never describe nationwide or default data as plot-specific. If coordinates are unavailable, do not claim to have checked local weather or soil. Use a place explicitly mentioned by the user as qualitative context, but ask for clarification if the place is ambiguous or appears only in an image.
    1. Processing Workflow:
       - Interpret the input and any attached media using only reliable evidence.
       - Reason internally in clear, concise English; never reveal internal reasoning.
       - Translate and adapt the final answer into the user's language using professional agronomic terminology.
       - Audio-specific rules: {PROMPTS.get("audio_instructions", [])}
    2. Visual Guardrail: If an image is present, prioritize visual inspection. NEVER confuse rice and cassava.
    3. Language & Output Protocol:
       - If audio is provided: Reply strictly in the language spoken in the voice message (French -> French, English -> English, Khmer -> Khmer).
       - If text is provided: If user writes French -> French. English -> English. Khmer -> Khmer.
       - If input is ambiguous or image-only without text -> DEFAULT TO KHMER.
       - Output Format: Provide ONLY the final response to the user in concise plain text (prefer at most five short bullets). Do not use Markdown or HTML syntax, including **, # headings, or backticks. Do NOT display intermediate reasoning or notes.
    4. Isolation of Greetings and Tests:
       - If User Query is a greeting, connectivity test, or single generic word (e.g., "test", "hello", "bonjour", "salut ca va"):
         * Simply acknowledge politely in the detected language and state readiness to assist with Cambodian agriculture.
         * DO NOT reference or continue previous disease diagnoses found in Recent Messages.
    5. Domain Scope & Guardrails:
       - Agroecology rules: {PROMPTS.get("agroecology_rules", [])}
       - Zero-hallucination rules: {PROMPTS.get("zero_hallucination_rules", [])}
       - SLCMV rules: {PROMPTS.get("slcmv_rules", [])}
       - If the user asks about non-agricultural topics (politics, general gossip, cryptocurrency, gaming, personal life, non-farming philosophy):
         * Refuse politely in the user's language.
         * Explicitly state: "{PROMPTS.get("off_topic_response", "I am an agricultural assistant.")}"
         * NEVER engage in casual chitchat or off-topic discussions.
    """

    llm_start = time.time()
    response_text, model_used = ask_llm(system_prompt, media_bytes=media_bytes, mime_type=media_mime)
    llm_ms = int((time.time() - llm_start) * 1000)
    total_ms = int((time.time() - t_start) * 1000)

    if not response_text:
        await status_msg.edit_text(ERR_MSGS.get(lang, ERR_MSGS["kh"]))
        return

    # Detect the final output language to align the feedback buttons
    resp_lang = detect_ui_lang(response_text)

    # 6. PostgreSQL audit trail
    interaction_id = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        raw_text_entry = user_text if user_text else ("[Voice message]" if has_voice else "[Photo sent]")
        current_role = access_control.get_user_role(telegram_id)
        cur.execute("""
            INSERT INTO interactions (
                telegram_id, role, has_text, has_photo, has_audio, raw_user_text, diagnosis_title,
                media_file_id, media_file_size_bytes, detected_language,
                latitude, longitude,
                rag_ms, llm_ms, total_ms, soil_source, model_used, confidence_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            telegram_id, current_role, bool(user_text), has_photo, has_voice, raw_text_entry, response_text[:100],
            media_file_id, media_file_size, lang,
            lat if telegram_id in USER_LOCATIONS else None,
            lon if telegram_id in USER_LOCATIONS else None,
            rag_ms, llm_ms, total_ms, soil_source_for_audit(soil), model_used, 90
        ))
        interaction_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"SQL insert error: {e}")

    # Align button labels with the actual language of the generated response
    btn_lbls = BUTTON_TEXTS.get(resp_lang, BUTTON_TEXTS["kh"])
    keyboard = [
        [
            InlineKeyboardButton(btn_lbls["pos"], callback_data=f"fb_pos_{resp_lang}_{interaction_id}"),
            InlineKeyboardButton(btn_lbls["neg"], callback_data=f"fb_neg_{resp_lang}_{interaction_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await status_msg.delete()
    await message.reply_text(to_telegram_plain_text(response_text), reply_markup=reply_markup)

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("set_lang_"):
        lang = data.replace("set_lang_", "")
        user = update.effective_user
        if user:
            access_control.set_user_language(user.id, lang)
            confirm_text = {
                "km": "✅ <b>ភាសារបស់អ្នកត្រូវបានផ្លាស់ប្តូរទៅជា ភាសាខ្មែរ ដោយជោគជ័យ!</b>",
                "en": "✅ <b>Your language has been successfully set to English!</b>",
                "fr": "✅ <b>Votre langue a été configurée sur Français avec succès !</b>"
            }.get(lang, "✅ Language updated / ភាសាត្រូវបានធ្វើបច្ចុប្បន្នភាព!")
            await query.edit_message_text(confirm_text, parse_mode="HTML")
        return

    parts = data.split("_")
    val = 1 if parts[1] == "pos" else -1
    lang = parts[2] if len(parts) >= 4 else "kh"
    interaction_id = parts[3] if len(parts) >= 4 else parts[-1]

    msg = FEEDBACK_MSGS.get(lang, FEEDBACK_MSGS["kh"])["pos" if val == 1 else "neg"]

    try:
        if interaction_id and interaction_id != "None":
            conn = psycopg2.connect(**DB_PARAMS)
            cur = conn.cursor()
            cur.execute("UPDATE interactions SET rating_thumb = %s WHERE id = %s AND rating_thumb IS NULL;", (val, int(interaction_id)))
            conn.commit()
            if cur.rowcount > 0:
                await context.bot.send_message(chat_id=query.message.chat_id, text=msg)

                if val == -1:
                    try:
                        cur.execute("SELECT telegram_id, raw_user_text, diagnosis_title FROM interactions WHERE id = %s;", (int(interaction_id),))
                        row = cur.fetchone()
                        if row:
                            fb_user_id, raw_q, diag_a = row
                            question_preview = (raw_q[:100] + "...") if raw_q and len(raw_q) > 100 else (raw_q or "[Sans texte]")
                            answer_preview = (diag_a[:100] + "...") if diag_a and len(diag_a) > 100 else (diag_a or "[Aucun diagnostic]")

                            admin_alert = (
                                f"⚠️ Alerte Feedback Négatif (👎)\n"
                                f"User: {fb_user_id}\n"
                                f"Question: {question_preview}\n"
                                f"Diagnostic: {answer_preview}"
                            )
                            try:
                                admin_id = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
                                if admin_id:
                                    asyncio.create_task(context.bot.send_message(chat_id=admin_id, text=admin_alert))
                            except Exception as task_err:
                                access_control.notify_admin_async(admin_alert)
                    except Exception as alert_err:
                        logger.error(f"Negative-feedback admin notification error: {alert_err}")
            else:
                logger.warning(f"Feedback ignoré (déjà renseigné) pour interaction {interaction_id}")
            cur.close()
            conn.close()
    except Exception as e:
        logger.error(f"Feedback SQL: {e}")

    await query.edit_message_reply_markup(reply_markup=None)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception non gérée : {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        msg_error = (
            "⚠️ **សុំទោស ប្រព័ន្ធកំពុងមានបញ្ហាបច្ចេកទេស ឬកំពុងថែទាំ។**\n"
            "សូមព្យាយាមម្តងទៀតនៅពេលបន្តិចក្រោយ។\n\n"
            "_(Désolé, le service rencontre une instabilité temporaire ou est en maintenance. "
            "Veuillez réessayer dans quelques instants.)_"
        )
        try:
            await update.effective_message.reply_text(msg_error, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(msg_error)

if __name__ == '__main__':
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quota", quota))
    application.add_handler(CommandHandler("usage", quota))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_input))
    application.add_handler(MessageHandler(filters.PHOTO, handle_user_input))
    application.add_handler(MessageHandler(filters.VOICE, handle_user_input))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(CallbackQueryHandler(handle_feedback))
    application.add_error_handler(error_handler)
    print("Krova Agri full RAG, vision, and voice stack is operational...")
    application.run_polling(drop_pending_updates=True)
