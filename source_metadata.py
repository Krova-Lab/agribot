"""Load and validate manually declared source metadata for RAG files."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


def source_manifest_path(filepath: str | Path) -> Path:
    return Path(filepath).with_suffix(".source.json")


def load_source_manifest(filepath: str | Path) -> tuple[dict, str | None]:
    """Read a source declaration; never mark a declaration as verified."""
    sidecar = source_manifest_path(filepath)
    if not sidecar.exists():
        return {}, None
    try:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"Invalid provenance sidecar: {type(exc).__name__}"
    if not isinstance(metadata, dict):
        return {}, "Provenance sidecar must contain a JSON object"
    source_url = str(metadata.get("source_url", "")).strip()
    if source_url:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {}, "source_url must be an absolute HTTP(S) URL"
    publication_date = str(metadata.get("publication_date", "")).strip()
    if publication_date:
        try:
            date.fromisoformat(publication_date)
        except ValueError:
            return {}, "publication_date must use YYYY-MM-DD"

    def clean(value: object) -> str:
        return str(value or "").replace("\x00", "").strip()

    return {
        "source_title": clean(metadata.get("source_title")),
        "source_url": source_url or None,
        "source_publisher": clean(metadata.get("publisher")) or None,
        "source_publication_date": publication_date or None,
        "source_license": clean(metadata.get("license")) or None,
        "source_locator": clean(metadata.get("page_or_section")) or None,
    }, None


def move_source_manifest(filepath: str | Path, destination: str | Path) -> None:
    sidecar = source_manifest_path(filepath)
    if sidecar.exists():
        shutil.move(str(sidecar), str(Path(destination) / sidecar.name))
