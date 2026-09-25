"""Lightweight language detection for the bot's supported UI languages."""

from __future__ import annotations

import re


def detect_ui_lang(text: str) -> str:
    """Return ``km``, ``fr``, or ``en`` using script and language markers."""
    if not text:
        return "km"

    if re.search(r"[\u1780-\u17FF]", text):
        return "km"

    lower_t = text.lower().strip()
    has_fr_accents = bool(re.search(r"[éèêëàâîïôùûç]", lower_t))
    fr_stop_words = {
        "le", "la", "les", "des", "du", "un", "une", "dans", "sur",
        "pour", "avec", "est", "c'est", "que", "qui", "je", "j", "tu",
        "vous", "mon", "ma", "mes", "peux", "peut", "dois", "veux",
    }
    fr_keywords = {
        "bonjour", "salut", "comment", "pourquoi", "maladie", "feuille",
        "riz", "culture", "engrais", "parasite",
    }

    words = set(re.findall(r"\b\w+\b", lower_t))
    if has_fr_accents or words.intersection(fr_keywords | fr_stop_words):
        return "fr"

    if re.search(r"[a-zA-Z]", text):
        return "en"

    return "km"
