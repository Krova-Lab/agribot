"""Shared PostgreSQL configuration for all Krova Agri services and tools."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DB_NAME = os.getenv("DB_NAME") or os.getenv("PGDATABASE")
DB_USER = os.getenv("DB_USER") or os.getenv("PGUSER")
DB_HOST = os.getenv("DB_HOST") or os.getenv("PGHOST")
DB_PORT = os.getenv("DB_PORT") or os.getenv("PGPORT")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD")


def get_db_params() -> dict[str, str | None]:
    """Return psycopg2-compatible connection parameters from shared config."""

    return {
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "host": DB_HOST,
        "port": DB_PORT,
        "connect_timeout": "3",
    }
