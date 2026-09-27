"""Run the small labelled RAG evaluation set against the configured database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag_search import retrieve_rag


DEFAULT_CASES = Path(__file__).resolve().parents[1] / "tests/fixtures/rag_eval.json"


def evaluate(cases_path: Path) -> tuple[bool, list[dict]]:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results = []
    all_ok = True
    for case in cases:
        retrieval = retrieve_rag(case["query"], limit=3, raise_on_error=True)
        urls = [source.url for source in retrieval.sources]
        if case["expected"] == "source":
            ok = case["expected_source_url"] in urls
        else:
            ok = not urls
        all_ok = all_ok and ok
        results.append(
            {
                "id": case["id"],
                "status": retrieval.status,
                "ok": ok,
                "metrics": retrieval.metrics or {},
                "source_urls": urls,
            }
        )
    return all_ok, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()
    try:
        all_ok, results = evaluate(args.cases)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)}))
        return 1
    print(json.dumps({"ok": all_ok, "cases": results}, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
