#!/usr/bin/env python3
"""Print a read-only operational summary of recent bot interactions."""

from __future__ import annotations

import argparse
import json
import sys

import psycopg2

from config.database import get_db_params


def build_report(days: int) -> dict:
    """Return aggregate metrics without selecting raw user content or media IDs."""
    if days < 1 or days > 365:
        raise ValueError("days must be between 1 and 365")
    conn = psycopg2.connect(**get_db_params())
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT
                   COUNT(*) AS requests,
                   COUNT(*) FILTER (WHERE has_photo OR has_audio OR has_video) AS media_requests,
                   percentile_cont(0.50) WITHIN GROUP (ORDER BY total_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms),
                   percentile_cont(0.50) WITHIN GROUP (ORDER BY rag_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY rag_ms),
                   percentile_cont(0.50) WITHIN GROUP (ORDER BY web_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY web_ms),
                   percentile_cont(0.50) WITHIN GROUP (ORDER BY llm_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY llm_ms),
                   COUNT(*) FILTER (WHERE evidence_trace->'telemetry'->'inference'->>'fallback_used' = 'true'),
                   COUNT(*) FILTER (WHERE evidence_trace->'grounding'->>'response_without_sources' = 'true'),
                   COUNT(*) FILTER (WHERE evidence_trace->>'response_status' = 'failed'),
                   COUNT(*) FILTER (WHERE web_ms IS NOT NULL),
                   COALESCE(SUM(estimated_cost_usd), 0)
              FROM interactions
             WHERE created_at >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')""",
            (days,),
        )
        row = cur.fetchone()
        cur.close()
        return {
            "window_days": days,
            "requests": row[0],
            "media_requests": row[1],
            "latency_ms": {
                "total_p50": row[2], "total_p95": row[3],
                "rag_p50": row[4], "rag_p95": row[5],
                "web_p50": row[6], "web_p95": row[7],
                "response_p50": row[8], "response_p95": row[9],
            },
            "fallback_requests": row[10],
            "responses_without_sources": row[11],
            "failed_responses": row[12],
            "web_research_requests": row[13],
            "estimated_cost_usd": float(row[14] or 0),
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Reporting window in days (1-365)")
    args = parser.parse_args()
    try:
        print(json.dumps(build_report(args.days), indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"Metrics report failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
