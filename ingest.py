"""Retired compatibility entry point for the provenance-aware ingester.

This module intentionally performs no database writes. Use ``ingest_files.py``
with a reviewed ``.source.json`` sidecar instead.
"""

from __future__ import annotations


def ingest() -> None:
    raise RuntimeError(
        "The legacy ingestion path is disabled. Use ingest_files.py with a reviewed source sidecar."
    )


if __name__ == "__main__":
    ingest()
