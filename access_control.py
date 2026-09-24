import time
import psycopg2
import os
import threading
import requests
from config.database import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

def notify_admin_async(message: str):
    """Send an asynchronous Telegram notification to the administrator without blocking."""
    def _send():
        try:
            token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
            if not token:
                return
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={"chat_id": ADMIN_TELEGRAM_ID, "text": message}, timeout=5)
        except Exception as e:
            print(f"Admin notification error: {e}")

    try:
        threading.Thread(target=_send, daemon=True).start()
    except Exception as e:
        print(f"Admin notification thread error: {e}")

DB_PASS = DB_PASSWORD

_ROLES_CACHE = {}
_SETTINGS_CACHE = {}
_LAST_CACHE_TIME = 0
CACHE_TTL = 30

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
    )

def refresh_cache_if_needed(force: bool = False):
    global _ROLES_CACHE, _SETTINGS_CACHE, _LAST_CACHE_TIME
    now = time.time()
    if force or (now - _LAST_CACHE_TIME > CACHE_TTL) or not _ROLES_CACHE:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT telegram_id, role, is_active, COALESCE(preferred_language, 'km'), COALESCE(admin_language, 'en') FROM bot_users")
            rows = cur.fetchall()
            _ROLES_CACHE = {row[0]: {"role": row[1], "is_active": row[2], "lang": row[3], "admin_lang": row[4]} for row in rows}

            cur.execute("SELECT key, value FROM bot_settings")
            s_rows = cur.fetchall()
            _SETTINGS_CACHE = {r[0]: r[1] for r in s_rows}

            _LAST_CACHE_TIME = now
            cur.close()
            conn.close()
        except Exception as e:
            print(f"bot_users cache sync error: {e}")

def get_max_pilot_users() -> int:
    refresh_cache_if_needed()
    raw_max = _SETTINGS_CACHE.get("max_pilot_users", 15)
    try:
        return int(raw_max)
    except (ValueError, TypeError):
        return 15

def get_user_role(telegram_id: int) -> str:
    refresh_cache_if_needed()
    user = _ROLES_CACHE.get(telegram_id)
    if not user or not user["is_active"]:
        return "guest"
    return user["role"]

def is_admin(telegram_id: int) -> bool:
    return get_user_role(telegram_id) == "admin"

def reset_ingestor_strikes(telegram_id: int) -> None:
    """Reset the temporary upload strike counter after an admin decision."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE ingestor_reputation SET strikes = 0 WHERE telegram_id = %s",
            (telegram_id,),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()

def is_allowed_access(telegram_id: int, username: str | None = None) -> bool:
    refresh_cache_if_needed()
    role = get_user_role(telegram_id)
    if role == "banned":
        return False
    
    mode = _SETTINGS_CACHE.get("access_mode", "pilot")
    if mode == "public":
        return True
    
    if role in ["admin", "tester", "user"]:
        return True

    if role == "guest" and mode == "pilot":
        max_pilot_users = get_max_pilot_users()

        active_pilot_users = sum(
            1 for u in _ROLES_CACHE.values()
            if u.get("is_active") and u.get("role") in ("admin", "tester", "user")
        )

        if active_pilot_users < max_pilot_users:
            set_user_role(telegram_id, "tester", username=username)
            places_restantes = max_pilot_users - (active_pilot_users + 1)
            uname = username.lstrip('@') if username else "None"
            msg = f"🔔 Nouveau testeur enrôlé : @{uname} (ID: {telegram_id}). Places restantes : {places_restantes}/15"
            notify_admin_async(msg)
            return True
        else:
            return False

    return False

def set_user_role(telegram_id: int, role: str, username: str | None = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bot_users (telegram_id, username, role, is_active, updated_at)
        VALUES (%s, %s, %s, TRUE, NOW())
        ON CONFLICT (telegram_id) DO UPDATE 
        SET role = EXCLUDED.role, is_active = TRUE, updated_at = NOW(),
            username = COALESCE(EXCLUDED.username, bot_users.username);
    """, (telegram_id, username, role))
    conn.commit()
    cur.close()
    conn.close()
    refresh_cache_if_needed(force=True)

def set_access_mode(mode: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bot_settings (key, value, updated_at)
        VALUES ('access_mode', %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
    """, (mode,))
    conn.commit()
    cur.close()
    conn.close()
    refresh_cache_if_needed(force=True)


def get_user_language(telegram_id: int) -> str:
    refresh_cache_if_needed()
    user = _ROLES_CACHE.get(telegram_id)
    if not user:
        return "km"
    return user.get("lang", "km")

def set_user_language(telegram_id: int, lang: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bot_users (telegram_id, preferred_language, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (telegram_id) DO UPDATE 
        SET preferred_language = EXCLUDED.preferred_language, updated_at = NOW();
    """, (telegram_id, lang))
    conn.commit()
    cur.close()
    conn.close()
    refresh_cache_if_needed(force=True)


def get_admin_language(telegram_id: int) -> str:
    refresh_cache_if_needed()
    user = _ROLES_CACHE.get(telegram_id)
    if not user:
        return "en"
    return user.get("admin_lang", "en")

def set_admin_language(telegram_id: int, lang: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bot_users (telegram_id, admin_language, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (telegram_id) DO UPDATE 
        SET admin_language = EXCLUDED.admin_language, updated_at = NOW();
    """, (telegram_id, lang))
    conn.commit()
    cur.close()
    conn.close()
    refresh_cache_if_needed(force=True)

def check_ingestor_rate_limit(telegram_id: int, max_per_window: int = 5, window_seconds: int = 600) -> tuple[bool, str]:
    """Limit submissions: max_per_window files every window_seconds (for example, 5 files / 10 minutes)."""
    now = time.time()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT strikes, window_count, window_start_ts FROM ingestor_reputation WHERE telegram_id = %s;", (telegram_id,))
        row = cur.fetchone()

        if not row:
            cur.execute("INSERT INTO ingestor_reputation (telegram_id, strikes, last_action_ts, window_count, window_start_ts) VALUES (%s, 0, %s, 1, %s);", (telegram_id, now, now))
            conn.commit()
            cur.close()
            conn.close()
            return True, ""

        strikes, count, w_start = row
        if now - w_start > window_seconds:
            # Reset the window
            cur.execute("UPDATE ingestor_reputation SET window_count = 1, window_start_ts = %s, last_action_ts = %s WHERE telegram_id = %s;", (now, now, telegram_id))
            conn.commit()
            cur.close()
            conn.close()
            return True, ""

        if count >= max_per_window:
            cur.close()
            conn.close()
            return False, f"Plafond atteint ({max_per_window} fichiers / {window_seconds // 60} min). Veuillez patienter."

        cur.execute("UPDATE ingestor_reputation SET window_count = window_count + 1, last_action_ts = %s WHERE telegram_id = %s;", (now, telegram_id))
        conn.commit()
        cur.close()
        conn.close()
        return True, ""
    except Exception as e:
        print(f"Rate-limit error: {e}")
        return True, ""

def record_ingestor_strike(telegram_id: int, max_strikes: int = 3) -> tuple[bool, int]:
    """Increment strikes. Disable the account when the error quota is exceeded."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ingestor_reputation (telegram_id, strikes, last_action_ts)
            VALUES (%s, 1, %s)
            ON CONFLICT (telegram_id)
            DO UPDATE SET strikes = ingestor_reputation.strikes + 1, last_action_ts = %s
            RETURNING strikes;
        """, (telegram_id, time.time(), time.time()))
        strikes = cur.fetchone()[0]

        is_banned = False
        if strikes >= max_strikes:
            cur.execute("UPDATE bot_users SET is_active = FALSE WHERE telegram_id = %s;", (telegram_id,))
            is_banned = True

        conn.commit()
        cur.close()
        conn.close()
        refresh_cache_if_needed(force=True)
        return is_banned, strikes
    except Exception as e:
        print(f"Strike-recording error: {e}")
        return False, 0

def get_user_daily_count(telegram_id: int) -> int:
    """Return the user's interaction count for today (since midnight)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM interactions
            WHERE telegram_id = %s AND created_at >= CURRENT_DATE;
        """, (telegram_id,))
        row = cur.fetchone()
        count = row[0] if row else 0
        cur.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Daily user-count error: {e}")
        return 0

_SLIDING_WINDOW_CACHE = {} # telegram_id -> list of timestamps

def check_user_rate_limit(telegram_id: int, max_per_minute: int = 5, max_per_day: int = 30) -> tuple[bool, str, int, int]:
    """
    Vérifie les limites de débit :
    - Limite glissante de sécurité : max 5 req / min
    - Plafond quotidien : max 30 req / jour
    Retourne (allowed, reason_code_or_msg, daily_count, remaining_today)
    """
    now = time.time()
    # 1. Sliding-window check (one minute)
    user_ts = _SLIDING_WINDOW_CACHE.get(telegram_id, [])
    user_ts = [t for t in user_ts if now - t < 60]
    if len(user_ts) >= max_per_minute:
        _SLIDING_WINDOW_CACHE[telegram_id] = user_ts
        daily_count = get_user_daily_count(telegram_id)
        return False, "minute_limit", daily_count, max(0, max_per_day - daily_count)

    # 2. Daily-limit check
    daily_count = get_user_daily_count(telegram_id)
    if daily_count >= max_per_day:
        return False, "daily_limit", daily_count, 0

    # Update the sliding window
    user_ts.append(now)
    _SLIDING_WINDOW_CACHE[telegram_id] = user_ts

    return True, "", daily_count, max_per_day - daily_count
