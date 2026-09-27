"""Verify that a request limit survives a process restart simulation."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

import access_control
import psycopg2
from config.database import get_db_params


CHILD_CHECK = "import access_control; print(access_control.check_user_rate_limit(%d, 1, 30))"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telegram-id", type=int, required=True)
    args = parser.parse_args()
    try:
        first = access_control.check_user_rate_limit(args.telegram_id, 1, 30)
        child_output = subprocess.check_output(
            [sys.executable, "-c", CHILD_CHECK % args.telegram_id],
            cwd=Path.cwd(),
            text=True,
        ).strip()
        second = ast.literal_eval(child_output.splitlines()[-1])
        print({"first_process": first, "second_process": second})
        return 0 if first[0] and second[1] == "minute_limit" else 1
    finally:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor()
        cur.execute("DELETE FROM request_rate_limits WHERE telegram_id = %s", (args.telegram_id,))
        conn.commit()
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
