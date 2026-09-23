#!/usr/bin/env python3
"""
bin/monitor_users.py
Compact dashboard for analysing the PostgreSQL 'interactions' table.

Displays:
1. Diagnoses per day.
2. Most active users (user_id / telegram_id).
3. Feedback ratio (positive versus negative).
"""

import os
import sys
import datetime
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.database import DB_HOST, DB_NAME, DB_PORT, DB_USER, DB_PASSWORD

# Load environment variables from .env (project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Shared PostgreSQL configuration is provided by config.database.
DB_PASS = DB_PASSWORD


def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"❌ PostgreSQL connection error for '{DB_NAME}' at {DB_HOST}:{DB_PORT}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Diagnoses per day
    cur.execute("""
        SELECT 
            DATE(created_at) AS date_diag,
            COUNT(*) AS total_diagnostics,
            COUNT(CASE WHEN rating_thumb = 1 THEN 1 END) AS positive_count,
            COUNT(CASE WHEN rating_thumb = -1 THEN 1 END) AS negative_count
        FROM interactions
        GROUP BY DATE(created_at)
        ORDER BY date_diag DESC;
    """)
    daily_stats: List[Dict[str, Any]] = cur.fetchall()  # type: ignore

    # 2. Most active users
    cur.execute("""
        SELECT 
            telegram_id AS user_id,
            COUNT(*) AS total_interactions,
            COUNT(CASE WHEN rating_thumb = 1 THEN 1 END) AS positive_feedbacks,
            COUNT(CASE WHEN rating_thumb = -1 THEN 1 END) AS negative_feedbacks,
            MAX(created_at) AS last_active
        FROM interactions
        GROUP BY telegram_id
        ORDER BY total_interactions DESC, last_active DESC
        LIMIT 10;
    """)
    top_users: List[Dict[str, Any]] = cur.fetchall()  # type: ignore

    # 3. Feedback ratio (positive versus negative)
    cur.execute("""
        SELECT 
            COUNT(*) AS total_interactions,
            COUNT(CASE WHEN rating_thumb IS NOT NULL THEN 1 END) AS rated_count,
            COUNT(CASE WHEN rating_thumb = 1 THEN 1 END) AS positive_count,
            COUNT(CASE WHEN rating_thumb = -1 THEN 1 END) AS negative_count,
            COUNT(CASE WHEN rating_thumb IS NULL OR rating_thumb = 0 THEN 1 END) AS unrated_count
        FROM interactions;
    """)
    feedback_stats_raw = cur.fetchone()
    feedback_stats: Dict[str, Any] = dict(feedback_stats_raw) if feedback_stats_raw else {}

    cur.close()
    conn.close()

    # Terminal formatting and display
    line = "=" * 80
    subline = "-" * 80

    print(line)
    print(" 📊 TABLEAU DE BORD DE SUIVI DES INTERACTIONS & UTILISATEURS")
    print(line)

    # Section 1: diagnoses per day
    print("\n📅 1. NOMBRE DE DIAGNOSTICS PAR JOUR")
    print(subline)
    if not daily_stats:
        print("  Aucune donnée enregistrée dans la table interactions.")
    else:
        headers = ["Date", "Nombre de diagnostics", "Retours 👍", "Retours 👎"]
        widths = [14, 25, 14, 14]

        def fmt_row(row):
            return "| " + " | ".join(f"{str(col):<{widths[i]}}" for i, col in enumerate(row)) + " |"

        sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        print(sep)
        print(fmt_row(headers))
        print(sep)
        for d in daily_stats:
            date_str = str(d['date_diag']) if d.get('date_diag') else "-"
            total_diag = d.get('total_diagnostics', 0)
            pos = d.get('positive_count', 0)
            neg = d.get('negative_count', 0)
            print(fmt_row([date_str, total_diag, pos, neg]))
        print(sep)

    # Section 2: top users
    print("\n🏆 2. TOP DES UTILISATEURS LES PLUS ACTIFS")
    print(subline)
    if not top_users:
        print("  Aucun utilisateur trouvé.")
    else:
        headers = ["Rank", "User ID (Telegram ID)", "Interactions", "Retours (👍/👎)", "Dernière activité"]
        widths = [6, 24, 14, 16, 20]

        def fmt_row_u(row):
            return "| " + " | ".join(f"{str(col):<{widths[i]}}" for i, col in enumerate(row)) + " |"

        sep_u = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        print(sep_u)
        print(fmt_row_u(headers))
        print(sep_u)
        for rank, u in enumerate(top_users, start=1):
            uid = str(u['user_id'])
            total_act = u.get('total_interactions', 0)
            pos = u.get('positive_feedbacks', 0)
            neg = u.get('negative_feedbacks', 0)
            fb_str = f"👍 {pos} / 👎 {neg}"
            dt = u.get('last_active')
            if isinstance(dt, datetime.datetime):
                dt_str = dt.strftime("%Y-%m-%d %H:%M")
            else:
                dt_str = str(dt)[:16] if dt else "-"
            print(fmt_row_u([f"#{rank}", uid, total_act, fb_str, dt_str]))
        print(sep_u)

    # Section 3: feedback ratio
    print("\n💬 3. RATIO DES RETOURS (FEEDBACK POSITIF VS NÉGATIF)")
    print(subline)
    tot = feedback_stats.get('total_interactions', 0)
    rated = feedback_stats.get('rated_count', 0)
    pos = feedback_stats.get('positive_count', 0)
    neg = feedback_stats.get('negative_count', 0)
    unrated = feedback_stats.get('unrated_count', 0)

    if rated > 0:
        pos_pct = (pos / rated) * 100
        neg_pct = (neg / rated) * 100
        ratio_str = f"{pos} : {neg} ({pos_pct:.1f}% Positif / {neg_pct:.1f}% Négatif)"
    else:
        ratio_str = "Aucun feedback explicite reçu (0 / 0)"

    print(f"  • Total d'interactions enregistrées : {tot}")
    print(f"  • Interactions évaluées            : {rated} (non évaluées : {unrated})")
    print(f"  • Retours positifs (👍)            : {pos}")
    print(f"  • Retours négatifs (👎)            : {neg}")
    print(f"  • Ratio Positif / Négatif          : {ratio_str}")
    print(line)
    print()


if __name__ == "__main__":
    main()
