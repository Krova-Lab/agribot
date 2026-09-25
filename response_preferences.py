"""Infer a user's preferred response detail level from recent explicit signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp
from typing import Iterable


DETAIL_REQUEST_TERMS = (
    "more detail", "more details", "explain further", "go deeper", "in detail",
    "plus de détails", "plus de detail", "davantage de détails", "davantage de detail",
    "explique davantage", "développe", "developpe", "en détail", "en detail",
    "plus d'informations", "plus d informations",
)


@dataclass(frozen=True)
class DetailSignal:
    requested_detail: bool
    created_at: datetime


def user_requests_more_detail(text: str | None) -> bool:
    """Detect an explicit request for a fuller answer, not a generic source request."""
    normalized = " ".join((text or "").lower().split())
    return any(term in normalized for term in DETAIL_REQUEST_TERMS)


def infer_detail_preference(signals: Iterable[DetailSignal]) -> tuple[str, float] | None:
    """Infer a preference from a recent rolling sample with time decay."""
    now = datetime.now(timezone.utc)
    recent = list(signals)[:20]
    if len(recent) < 5:
        return None

    weighted_total = 0.0
    weighted_detail = 0.0
    detail_count = 0
    for signal in recent:
        timestamp = signal.created_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - timestamp).total_seconds() / 86400)
        weight = exp(-age_days / 45.0)
        weighted_total += weight
        if signal.requested_detail:
            detail_count += 1
            weighted_detail += weight

    ratio = weighted_detail / weighted_total if weighted_total else 0.0
    if detail_count >= 3 and ratio >= 0.30:
        return "detailed", round(ratio, 3)
    return None
