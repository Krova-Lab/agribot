#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeDefault
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import access_control
import doc_auditor
from config.database import PROJECT_ROOT

load_dotenv()
TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
DROPZONE = str(PROJECT_ROOT / "rag_dropzone")
os.makedirs(DROPZONE, exist_ok=True)

if not TOKEN:
    print("❌ TELEGRAM_ADMIN_BOT_TOKEN manquant dans .env")
    sys.exit(1)

SUPPORTED_EXT = {
    ".pdf", ".txt", ".md", ".docx", ".doc", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"
}

MESSAGES = {
    "fr": {
        "unauthorized": "⛔ Accès non autorisé à cette console.",
        "start": (
            "🛠 **KhmerAgri Console Admin & Ingestion**\n\n"
            "• Déposez ici vos documents (PDF, DOCX, XLSX, TXT, Scans).\n"
            "• Indexation automatique par le daemon RAG.\n\n"
            "📌 **Commandes :**\n"
            "/status - État dropzone et base vectorielle\n"
            "/stats - Statistiques et latences\n"
            "/mode <pilot|public> - Changer le mode d'accès public\n"
            "/promote <id> <role> - Gérer les rôles\n"
            "/settings - Changer la langue de la console"
        ),
        "status_title": "📊 **État du système KhmerAgri**",
        "mode_label": "Mode d'accès public",
        "chunks_label": "Chunks en base",
        "dropzone_label": "Fichiers dans la dropzone",
        "none": "Aucun",
        "more": "et {} autre(s)",
        "recv": "📥 Réception de `{}`...",
        "ingest_ok": "✓ Fichier `{}` placé dans la dropzone (indexation auto).",
        "scan_ok": "✓ Scan `{}` placé dans la dropzone pour vectorisation.",
        "bad_format": "❌ Format non supporté. Formats acceptés : PDF, DOCX, XLSX, TXT, MD, Images.",
        "lang_set": "✓ Langue de la console définie sur : **Français**."
    },
    "km": {
        "unauthorized": "⛔ គ្មានការអនុញ្ញាតចូលប្រើប្រាស់។",
        "start": (
            "🛠 **ផ្ទាំងគ្រប់គ្រង និងបញ្ចូលឯកសារ (KhmerAgri Console)**\n\n"
            "• សូមផ្ញើឯកសារកសិកម្មនៅទីនេះ (PDF, DOCX, XLSX, TXT, រូបភាពស្កេន)។\n"
            "• ឯកសារនឹងត្រូវបញ្ចូលទៅក្នុងប្រព័ន្ធស្វ័យប្រវត្តិ (RAG Vectorization)។\n\n"
            "📌 **ពាក្យបញ្ជា :**\n"
            "/status - ពិនិត្យស្ថានភាពឯកសារ និងទិន្នន័យ\n"
            "/stats - ស្ថិតិប្រើប្រាស់ និងល្បឿនប្រព័ន្ធ\n"
            "/mode <pilot|public> - ប្តូររបៀបដំណើរការ\n"
            "/promote <id> <role> - កំណត់សិទ្ធិអ្នកប្រើប្រាស់\n"
            "/settings - កំណត់ភាសារបស់ផ្ទាំងគ្រប់គ្រង"
        ),
        "status_title": "📊 **ស្ថានភាពប្រព័ន្ធ (KhmerAgri Status)**",
        "mode_label": "របៀបដំណើរការសាធារណៈ",
        "chunks_label": "ចំនួន Chunks ក្នុង Base",
        "dropzone_label": "ឯកសាររង់ចាំក្នុង Dropzone",
        "none": "គ្មានឯកសារ",
        "more": "និង {} ទៀត",
        "recv": "📥 កំពុងទទួល `{}`...",
        "ingest_ok": "✓ ឯកសារ `{}` ត្រូវបានដាក់ចូលក្នុង Dropzone រួចរាល់។",
        "scan_ok": "✓ រូបភាពស្កេន `{}` ត្រូវបានដាក់ចូលក្នុង Dropzone រួចរាល់។",
        "bad_format": "❌ ប្រភេទឯកសារមិនត្រឹមត្រូវ។ ឯកសារដែលអនុញ្ញាត: PDF, DOCX, XLSX, TXT, MD, រូបភាព។",
        "lang_set": "✓ ភាសាផ្ទាំងគ្រប់គ្រងត្រូវបានប្តូរទៅជា: **ភាសាខ្មែរ**។"
    },
    "en": {
        "unauthorized": "⛔ Unauthorized access.",
        "start": (
            "🛠 **KhmerAgri Console Admin & Ingestion**\n\n"
            "• Drop agricultural documents here (PDF, DOCX, XLSX, TXT, Scans).\n"
            "• Automatic vector indexing via RAG daemon.\n\n"
            "📌 **Commands :**\n"
            "/status - Dropzone and DB status\n"
            "/stats - System metrics and latency\n"
            "/mode <pilot|public> - Switch public access mode\n"
            "/promote <id> <role> - Manage user roles\n"
            "/settings - Change console language"
        ),
        "status_title": "📊 **KhmerAgri System Status**",
        "mode_label": "Public access mode",
        "chunks_label": "Chunks in database",
        "dropzone_label": "Pending dropzone files",
        "none": "None",
        "more": "and {} more",
        "recv": "📥 Receiving `{}`...",
        "ingest_ok": "✓ File `{}` placed in dropzone (auto-indexing).",
        "scan_ok": "✓ Scan `{}` placed in dropzone for vectorization.",
        "bad_format": "❌ Unsupported format. Allowed: PDF, DOCX, XLSX, TXT, MD, Images.",
        "lang_set": "✓ Console language set to: **English**."
    }
}

ADMIN_NOTIFY_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
MAX_FILE_SIZE = 19.5 * 1024 * 1024  # 19.5 MB

def is_authorized(user_id: int) -> bool:
    role = access_control.get_user_role(user_id)
    return role in ["admin", "ingestor"]

def get_admin_lang(user_id: int) -> str:
    # TODO: keep this per-admin and extend language coverage across every console message.
    lang = access_control.get_admin_language(user_id)
    return lang if lang in MESSAGES else "en"

def get_lang_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="adminlang_km"),
            InlineKeyboardButton("🇫🇷 Français", callback_data="adminlang_fr"),
            InlineKeyboardButton("🇬🇧 English", callback_data="adminlang_en"),
        ]
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    l = get_admin_lang(user_id)
    await update.message.reply_text(MESSAGES[l]["start"], parse_mode="Markdown")

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return
    await update.message.reply_text(
        "🌐 Choisissez la langue de la console d'administration / Choose console language :",
        reply_markup=get_lang_keyboard()
    )

async def handle_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    lang = query.data.split("_")[1]
    access_control.set_admin_language(user_id, lang)
    msg = MESSAGES.get(lang, MESSAGES["en"])["lang_set"]
    await query.edit_message_text(msg, parse_mode="Markdown")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    l = get_admin_lang(user_id)
    t = MESSAGES[l]

    try:
        pending = [f for f in os.listdir(DROPZONE) if not f.startswith('.')]

        conn = access_control.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM rag_documents")
        chunks = cur.fetchone()[0]
        cur.execute("SELECT value FROM bot_settings WHERE key = 'access_mode'")
        mode = cur.fetchone()
        current_mode = mode[0] if mode else "inconnu"
        cur.close()
        conn.close()

        files_list = "\n".join([f"  • {f}" for f in pending[:5]]) if pending else f"  ({t['none']})"
        if len(pending) > 5:
            files_list += f"\n  ...{t['more'].format(len(pending) - 5)}"

        await update.message.reply_text(
            f"{t['status_title']}\n\n"
            f"• {t['mode_label']} : `{current_mode}`\n"
            f"• {t['chunks_label']} : `{chunks}`\n"
            f"• {t['dropzone_label']} : `{len(pending)}`\n{files_list}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"Erreur status : {e}")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return
    try:
        conn = access_control.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), AVG(total_ms) FROM interactions")
        total, avg_ms = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM bot_users WHERE is_active = TRUE")
        nb_users = cur.fetchone()[0]
        cur.close()
        conn.close()
        avg_ms = int(avg_ms) if avg_ms else 0
        await update.message.reply_text(
            f"📈 **Métriques / Stats** :\n"
            f"- Interactions : {total}\n"
            f"- Latence moy : {avg_ms} ms\n"
            f"- Users actifs : {nb_users}"
        )
    except Exception as e:
        await update.message.reply_text(f"Erreur stats : {e}")

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not access_control.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Réservé aux administrateurs.")
        return
    if not context.args or context.args[0] not in ["pilot", "public"]:
        await update.message.reply_text("Usage : /mode <pilot|public>")
        return
    mode = context.args[0]
    access_control.set_access_mode(mode)
    await update.message.reply_text(f"✓ Mode basculé : `{mode}`")

async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not access_control.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Réservé aux administrateurs.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage : /promote <telegram_id> <admin|ingestor|tester|user|banned>")
        return
    try:
        target_id = int(context.args[0])
        role = context.args[1].lower()
        if role not in ["admin", "ingestor", "tester", "user", "banned"]:
            await update.message.reply_text("Rôle invalide.")
            return
        access_control.set_user_role(target_id, role)
        access_control.reset_ingestor_strikes(target_id)
        await update.message.reply_text(f"✓ Rôle mis à jour et strikes réinitialisés : {target_id} -> `{role}`")
    except ValueError:
        await update.message.reply_text("L'ID doit être un entier.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    l = get_admin_lang(user_id)
    t = MESSAGES[l]

    # Rate-limit check (5 files / 10 minutes)
    allowed, err_msg = access_control.check_ingestor_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"⏳ **Ralentissement requis** : {err_msg}")
        return

    doc = update.message.document
    file_name = doc.file_name or "document.pdf"
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in SUPPORTED_EXT:
        is_banned, strikes = access_control.record_ingestor_strike(user_id)
        if is_banned:
            await update.message.reply_text("⛔ **Compte suspendu** suite à des envois répétés de fichiers non conformes.")
            await context.bot.send_message(
                chat_id=ADMIN_NOTIFY_ID,
                text=f"🚨 **Alerte Sécurité** : Ingestor `{user_id}` révoqué automatiquement (3 avertissements)."
            )
        else:
            await update.message.reply_text(f"{t['bad_format']}\n⚠️ Avertissement {strikes}/3 avant suspension.")
        return

    # Check the size BEFORE any network call
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        size_mb = round(doc.file_size / (1024 * 1024), 1)
        await update.message.reply_text(
            f"❌ **Fichier trop volumineux ({size_mb} Mo)**.\n\n"
            f"L'API Telegram standard bloque le téléchargement par bot au-delà de **20 Mo**.\n\n"
            f"💡 **Solutions :**\n"
            f"1. Compressez le PDF sous 20 Mo.\n"
            f"2. Ou déposez directement le gros fichier sur le serveur via SCP/SFTP dans :\n"
            f"`{DROPZONE}/`",
            parse_mode="Markdown"
        )
        return

    dest = os.path.join(DROPZONE, file_name)
    await update.message.reply_text(t["recv"].format(file_name), parse_mode="Markdown")

    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=dest)

    # Duplicate SHA-256 audit
        file_sha = doc_auditor.compute_file_sha256(dest)
        is_dup, reason = doc_auditor.check_duplicate(file_sha)
        if is_dup:
            os.remove(dest)
            await update.message.reply_text(f"⚠️ **Fichier ignoré** : {reason}")
            return

        await update.message.reply_text(t["ingest_ok"].format(file_name), parse_mode="Markdown")

    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        await update.message.reply_text(f"❌ Erreur lors du téléchargement : {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    # Rate limiting for scans
    allowed, err_msg = access_control.check_ingestor_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"⏳ **Ralentissement requis** : {err_msg}")
        return

    l = get_admin_lang(user_id)
    t = MESSAGES[l]

    photo = update.message.photo[-1]
    file_name = f"scan_{photo.file_unique_id}.jpg"
    dest = os.path.join(DROPZONE, file_name)

    await update.message.reply_text(t["recv"].format(file_name), parse_mode="Markdown")
    try:
        tg_file = await photo.get_file()
        await tg_file.download_to_drive(custom_path=dest)
        await update.message.reply_text(t["scan_ok"].format(file_name), parse_mode="Markdown")
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        await update.message.reply_text(f"❌ Erreur lors du téléchargement de l'image : {e}")

def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("promote", cmd_promote))
    app.add_handler(CallbackQueryHandler(handle_lang_callback, pattern="^adminlang_"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("✓ Bot Admin multilingue prêt.")
    app.run_polling()

if __name__ == "__main__":
    main()
