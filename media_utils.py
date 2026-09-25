"""Bounded media validation and normalization for Telegram inputs."""

from __future__ import annotations

import io

from PIL import Image


def enforce_download_limit(payload: bytes, maximum_bytes: int, media_label: str) -> None:
    """Reject a downloaded payload even when Telegram metadata was absent."""

    if len(payload) > maximum_bytes:
        raise ValueError(f"{media_label} exceeds the configured download limit")


def normalize_image(payload: bytes, maximum_bytes: int) -> bytes:
    """Decode, resize, and re-encode an image before external processing."""

    enforce_download_limit(payload, maximum_bytes, "Image")
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image = image.convert("RGB")
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
            normalized = output.getvalue()
    except Exception as exc:
        raise ValueError("Image decoding or normalization failed") from exc
    enforce_download_limit(normalized, maximum_bytes, "Normalized image")
    return normalized
