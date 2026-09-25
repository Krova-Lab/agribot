"""Dedicated PostgreSQL configuration for the future public bot."""

from __future__ import annotations

import os


def get_prod_db_params() -> dict[str, str]:
    """Return production-bot DB parameters without falling back to pilot DB values."""

    required = {
        "dbname": os.getenv("PROD_DB_NAME"),
        "user": os.getenv("PROD_DB_USER"),
        "password": os.getenv("PROD_DB_PASSWORD"),
        "host": os.getenv("PROD_DB_HOST", "127.0.0.1"),
        "port": os.getenv("PROD_DB_PORT", "5432"),
        "connect_timeout": "3",
    }
    missing = [name for name in ("dbname", "user", "password") if not required[name]]
    if missing:
        raise RuntimeError("Missing dedicated production database settings: " + ", ".join(missing))
    return {key: value for key, value in required.items() if value is not None}
