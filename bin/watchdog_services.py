#!/usr/bin/env python3
"""
bin/watchdog_services.py
Proactive monitoring for Krova Agri services:
- krova-agribot.service (Telegram bot engine)
- khmeragri-api.service (FastAPI REST API)
- khmeragri-admin.service (admin bot & gateway)
- HTTP endpoint /api/v1/health

On failure:
1. Attempt an automatic restart.
2. Send an immediate Telegram alert to the configured administrator.
3. Send a recovery notification when the system becomes healthy again.
"""

import os
import sys
import json
import time
import subprocess
import requests
from config.database import PROJECT_ROOT
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
STATE_FILE = str(PROJECT_ROOT / "watchdog_state.json")

SERVICES = [
    "krova-agribot.service",
    "khmeragri-api.service",
    "khmeragri-admin.service"
]

HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"

def send_telegram_alert(text: str):
    if not TELEGRAM_TOKEN:
        print("[Watchdog] No Telegram token configured for alerts.", file=sys.stderr)
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": ADMIN_TELEGRAM_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=8)
        return resp.status_code == 200
    except Exception as e:
        print(f"[Watchdog] Telegram alert error: {e}", file=sys.stderr)
        return False

def check_service_active(service_name: str) -> bool:
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return res.stdout.strip() == "active"
    except Exception:
        return False

def restart_service(service_name: str) -> bool:
    try:
        res = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15
        )
        return res.returncode == 0
    except Exception:
        return False

def check_api_health() -> bool:
    try:
        resp = requests.get(HEALTH_URL, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("status") == "healthy"
        return False
    except Exception:
        return False

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_status": "ok", "last_alert_time": 0, "failures": []}

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"[Watchdog] State save error: {e}", file=sys.stderr)

def main():
    state = load_state()
    now = time.time()
    errors = []

    # 1. Check systemd services
    for s in SERVICES:
        if not check_service_active(s):
            print(f"[Watchdog] Service inactive: {s}. Attempting restart...")
            restart_service(s)
            time.sleep(2)
            if not check_service_active(s):
                errors.append(f"❌ Service {s} failed (automatic restart unsuccessful)")
            else:
                print(f"[Watchdog] Service {s} restarted successfully.")

    # 2. Check the HTTP API endpoint
    if not check_api_health():
        print("[Watchdog] Endpoint /api/v1/health injoignable ou non sain. Relance API...")
        restart_service("khmeragri-api.service")
        time.sleep(2)
        if not check_api_health():
            errors.append("❌ Backend API REST (/api/v1/health) hors-service")
        else:
            print("[Watchdog] REST API backend restored.")

    # 3. Manage alerts and service lifecycle
    if errors:
        print(f"[Watchdog] Errors detected: {errors}")
        # Anti-spam: alert only if the previous state was 'ok' or more than 30 minutes have elapsed
        if state.get("last_status") == "ok" or (now - state.get("last_alert_time", 0) > 1800):
            msg = (
                "🚨 <b>[Krova Agri Watchdog] Incident detected</b>\n\n"
                + "\n".join(errors) +
                f"\n\n⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                "ℹ️ Automatic recovery attempts were triggered."
            )
            send_telegram_alert(msg)
            state["last_status"] = "error"
            state["last_alert_time"] = now
            state["failures"] = errors
            save_state(state)
    else:
        # If recovering from an error state, send a recovery message
        if state.get("last_status") == "error":
            recovery_msg = (
                "✅ <b>[Krova Agri Watchdog] Full recovery</b>\n\n"
                "All services (Telegram bot, REST API, and admin gateway) are active and healthy again.\n"
                f"⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram_alert(recovery_msg)
            print("[Watchdog] Recovery notification sent.")

        state["last_status"] = "ok"
        state["last_alert_time"] = 0
        state["failures"] = []
        save_state(state)
        print("[Watchdog] All services and endpoints are operational (OK).")

if __name__ == "__main__":
    main()
