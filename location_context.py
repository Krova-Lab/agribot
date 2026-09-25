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
            "No plot-specific soil lookup: no coordinates were supplied. Use Cambodia-wide agronomic context only; do not infer this plot's soil properties.",
            "No plot-specific weather lookup: no coordinates were supplied. Use Cambodia-wide seasonal context only; do not claim current local weather.",
            "Cambodia-wide baseline; no specific location confirmed. Use any place named in the user's message as qualitative regional context, without treating it as plot-level evidence.",
        )

    lat, lon = coordinates
    return (
        lat,
        lon,
        soil_lookup(lat, lon),
        weather_lookup(lat, lon),
        f"Cambodia; user-shared coordinates: {lat}, {lon}",
    )
