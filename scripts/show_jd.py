"""Print one enriched JD to eyeball extraction quality."""

from __future__ import annotations

import sqlite3


def main() -> int:
    conn = sqlite3.connect("data/jobs.db")
    row = conn.execute(
        "SELECT title, company, length(description), description FROM jobs "
        "WHERE source='jobstreet' ORDER BY score DESC LIMIT 1"
    ).fetchone()
    title, company, length, description = row
    print(f"{title} @ {company}  ({length} chars)")
    print("-" * 70)
    print(description[:900])
    print("-" * 70)
    total, with_jd = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN length(description) > 300 THEN 1 ELSE 0 END) FROM jobs"
    ).fetchone()
    print(f"JD coverage: {with_jd}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
