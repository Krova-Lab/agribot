#!/usr/bin/env python3
"""Compare configured models on the same private, labeled task cases."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_adapter import ask_llm, configured_routes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path, help="JSONL file with id, task, prompt, and optional media_path/mime_type")
    parser.add_argument("--output", type=Path, default=Path("runtime/model-eval.jsonl"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.cases.open(encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as report:
        for line in source:
            if not line.strip():
                continue
            case = json.loads(line)
            task = case["task"]
            media_path = Path(case["media_path"]) if case.get("media_path") else None
            media = media_path.read_bytes() if media_path else None
            for route in configured_routes(task):
                started = time.monotonic()
                answer, used = ask_llm(
                    case["prompt"],
                    media_bytes=media,
                    mime_type=case.get("mime_type", "image/jpeg"),
                    model_name=route.label,
                    task=task,
                )
                result = {
                    "case_id": case["id"],
                    "task": task,
                    "model": used,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "success": bool(answer),
                    "answer": answer,
                }
                report.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(f"{case['id']} {used} {'ok' if answer else 'failed'} {result['latency_ms']}ms")
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
