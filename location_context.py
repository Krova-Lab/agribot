"""Build agricultural context without inventing a user's plot location."""

from __future__ import annotations

from typing import Any, Callable


def soil_source_for_audit(soil: Any) -> str | None:
    """Return a source only when soil data came from a structured lookup."""

    if not isinstance(soil, dict):
        return None
    source = soil.get("source")
    return source if isinstance(source, str) else None


def build_location_context(
    coordinates: tuple[float, float] | None,
    soil_lookup: Callable[[float, float], Any],
    weather_lookup: Callable[[float, float], Any],
) -> tuple[float | None, float | None, Any, Any, str]:
    """Fetch plot data only for coordinates explicitly shared by the user."""

    if coordinates is None:
        return (
            None,
            None,
            "Unavailable: no coordinates supplied; do not infer plot soil properties.",
            "Unavailable: no coordinates supplied; do not infer local weather.",
            "Cambodia; no specific location confirmed. Consider any place named in the user's message as qualitative context.",
        )

    lat, lon = coordinates
    return (
        lat,
        lon,
        soil_lookup(lat, lon),
        weather_lookup(lat, lon),
        f"Cambodia; user-shared coordinates: {lat}, {lon}",
    )
