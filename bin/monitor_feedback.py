#!/usr/bin/env python3
"""
bin/monitor_feedback.py
Script for tracking overall satisfaction, the beta-tester quota,
and the five most recent interactions recorded in the configured PostgreSQL database.
"""

import os
import sys
import datetime
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.database import DB_HOST, DB_NAME, DB_PORT, DB_USER, DB_PASSWORD

# PostgreSQL connection settings are provided by config.database.
DB_PASS = DB_PASSWORD

QUOTA_MAX_TESTERS = 15

def truncate_text(text: Optional[str], max_len: int = 32) -> str:
    if not text:
        return "-"
    text_clean = " ".join(text.split())
    if len(text_clean) > max_len:
        return text_clean[:max_len - 3] + "..."
    return text_clean

def format_rating(rating: Optional[int]) -> str:
    if rating == 1:
        return "👍"
    elif rating == -1:
        return "👎"
    return "—"

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"❌ PostgreSQL connection error ({DB_NAME}): {e}", file=sys.stderr)
        sys.exit(1)

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Overall satisfaction rate
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE rating_thumb = 1) AS thumbs_up,
            COUNT(*) FILTER (WHERE rating_thumb = -1) AS thumbs_down,
            COUNT(*) FILTER (WHERE rating_thumb IS NOT NULL AND rating_thumb != 0) AS total_rated
        FROM interactions;
    """)
    sat_row: Optional[Dict[str, Any]] = cur.fetchone()  # type: ignore
    thumbs_up = int(sat_row['thumbs_up']) if sat_row and sat_row.get('thumbs_up') is not None else 0
    thumbs_down = int(sat_row['thumbs_down']) if sat_row and sat_row.get('thumbs_down') is not None else 0
    total_rated = int(sat_row['total_rated']) if sat_row and sat_row.get('total_rated') is not None else 0

    satisfaction_rate = (thumbs_up / total_rated * 100) if total_rated > 0 else 0.0

    # 2. Enrolled tester count
    cur.execute("""
        SELECT COUNT(*) AS active_users
        FROM bot_users
        WHERE is_active = true;
    """)
    user_row: Optional[Dict[str, Any]] = cur.fetchone()  # type: ignore
    active_users = int(user_row['active_users']) if user_row and user_row.get('active_users') is not None else 0
    remaining_slots = max(0, QUOTA_MAX_TESTERS - active_users)

    # 3. Five most recently recorded interactions
    cur.execute("""
        SELECT 
            id,
            created_at,
            telegram_id,
            raw_user_text,
            has_photo,
            has_audio,
            diagnosis_title,
            rating_thumb
        FROM interactions
        ORDER BY created_at DESC
        LIMIT 5;
    """)
    interactions: list[Dict[str, Any]] = cur.fetchall()  # type: ignore

    cur.close()
    conn.close()

    # --- Terminal display ---
    line = "=" * 90
    subline = "-" * 90

    print(line)
    print(" 📊 FEEDBACK AND TESTER MONITORING DASHBOARD (Krova Agri)")
    print(line)

    print("\n1. OVERALL SATISFACTION RATE")
    print(subline)
    print(f"  • Positive votes (👍)  : {thumbs_up}")
    print(f"  • Negative votes (👎)  : {thumbs_down}")
    print(f"  • Satisfaction rate    : {satisfaction_rate:.1f}% ({total_rated} vote(s) cast)")

    print("\n2. ENROLLED TESTER COUNT")
    print(subline)
    print(f"  • Active users         : {active_users} / {QUOTA_MAX_TESTERS}")
    print(f"  • Remaining places     : {remaining_slots}")

    print("\n3. 5 MOST RECENT RECORDED INTERACTIONS")
    print(subline)

    headers = ["Timestamp", "User ID", "Question preview", "Diagnosis / response", "Rating"]
    col_widths = [16, 12, 25, 25, 6]

    def build_row(cols):
        return "| " + " | ".join(f"{str(col):<{col_widths[i]}}" for i, col in enumerate(cols)) + " |"

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    print(sep)
    print(build_row(headers))
    print(sep)

    if not interactions:
        total_width = sum(col_widths) + 3 * (len(col_widths) - 1)
        print("| " + f"{'No interactions recorded':^{total_width}}" + " |")
        print(sep)
    else:
        for item in interactions:
            dt = item['created_at']
            if isinstance(dt, datetime.datetime):
                dt_str = dt.strftime("%Y-%m-%d %H:%M")
            else:
                dt_str = str(dt)[:16] if dt else "-"

            user_id = str(item['telegram_id'])

            question = item.get('raw_user_text')
            if not question:
                if item.get('has_photo'):
                    question = "[Photo]"
                elif item.get('has_audio'):
                    question = "[Audio]"
                else:
                    question = "[Sans texte]"

            question_preview = truncate_text(question, col_widths[2])
            diag_title = item.get('diagnosis_title') or "[No diagnosis]"
            diag_preview = truncate_text(diag_title, col_widths[3])
            rating_str = format_rating(item.get('rating_thumb'))

            print(build_row([dt_str, user_id, question_preview, diag_preview, rating_str]))
        print(sep)

    print()

if __name__ == "__main__":
    main()
