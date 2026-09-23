"""Shared runtime settings for local tools and test utilities."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from config.database import PROJECT_ROOT


load_dotenv(PROJECT_ROOT / ".env")

TESTER_TELEGRAM_ID = int(os.getenv("TESTER_TELEGRAM_ID", "999999999"))
