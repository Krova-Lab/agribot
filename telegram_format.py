"""Keep generated Telegram replies readable without relying on model-safe markup."""

from __future__ import annotations

import re


def to_telegram_plain_text(response: str) -> str:
    """Remove common generated Markdown markers while preserving the wording."""

    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", response)
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?<!`)`(?!`)", "", text)
    return text.strip()
