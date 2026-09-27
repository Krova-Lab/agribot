"""Exercise the persistent request limiter with concurrent temporary requests."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import access_control
import psycopg2
from config.database import get_db_params


def run(telegram_id: int, requests: int, per_minute: int) -> bool:
    try:
        with ThreadPoolExecutor(max_workers=requests) as pool:
            results = list(
                pool.map(
                    lambda _: access_control.check_user_rate_limit(
                        telegram_id, max_per_minute=per_minute, max_per_day=30
                    ),
                    range(requests),
                )
            )
        allowed = sum(result[0] for result in results)
        rejected = sum(result[1] == "minute_limit" for result in results)
        print({"allowed": allowed, "minute_rejected": rejected, "requests": requests})
        return allowed == per_minute and rejected == requests - per_minute
    finally:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor()
        cur.execute("DELETE FROM request_rate_limits WHERE telegram_id = %s", (telegram_id,))
        conn.commit()
        cur.close()
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telegram-id", type=int, required=True)
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--per-minute", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.per_minute < args.requests:
        parser.error("--per-minute must be positive and lower than --requests")
    return 0 if run(args.telegram_id, args.requests, args.per_minute) else 1


if __name__ == "__main__":
    raise SystemExit(main())
