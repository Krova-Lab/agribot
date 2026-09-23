"""Utilities for safely deriving filesystem path segments from labels."""

from __future__ import annotations

import re


def safe_slug(value: str, fallback: str) -> str:
    """Turn user-provided labels into bounded, filesystem-safe path segments."""

    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("._")
    return slug[:80] or fallback
