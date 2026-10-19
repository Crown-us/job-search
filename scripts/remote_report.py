"""Remote feed results: what came in, and the best of it."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db

FEEDS = ("remoteok", "remotive", "jobicy", "himalayas", "arbeitnow")


def main() -> int:
    conn = db.connect()
    placeholders = ",".join("?" * len(FEEDS))
    print("per sumber:")
    for row in conn.execute(
        f"SELECT source, COUNT(*), SUM(remote) FROM jobs WHERE source IN ({placeholders}) GROUP BY source",
        FEEDS,
    ):
        print(f"  {row[0]:<10} total={row[1]:<4} remote={row[2]}")

    print("\ntop 12 remote feed:")
    rows = conn.execute(
        f"""
        SELECT title, company, location, source, score
        FROM jobs WHERE source IN ({placeholders}) AND status = 'new'
        ORDER BY score DESC LIMIT 12
        """,
        FEEDS,
    ).fetchall()
    for title, company, location, source, score in rows:
        print(f"  {score:>3}  {title[:44]:<46} {company[:20]:<22} {location[:26]:<28} {source}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
