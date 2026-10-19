"""Mark the current top-N shortlist as already delivered, for one channel.

Needed once, when delivery tracking is introduced after messages have already
been sent by hand.

Run: python scripts/mark_sent.py discord 5 70
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db


def main(argv: list[str]) -> int:
    channel = argv[0] if argv else "discord"
    limit = int(argv[1]) if len(argv) > 1 else 5
    min_fit = int(argv[2]) if len(argv) > 2 else 70

    conn = db.connect()  # creates the deliveries table if this is the first run
    rows = conn.execute(
        """
        SELECT j.id, j.title
        FROM jobs j LEFT JOIN analyses a ON a.job_id = j.id
        WHERE j.status IN ('new', 'shortlist') AND COALESCE(a.fit, j.score, 0) >= ?
        ORDER BY COALESCE(a.fit, j.score, 0) DESC, j.score DESC
        LIMIT ?
        """,
        (min_fit, limit),
    ).fetchall()
    conn.executemany(
        "INSERT OR IGNORE INTO deliveries (job_id, channel, sent_at) VALUES (?, ?, datetime('now'))",
        [(row[0], channel) for row in rows],
    )
    conn.commit()
    print(f"marked {len(rows)} job(s) as delivered to {channel}:")
    for row in rows:
        print(f"  {row[0][:8]}  {row[1][:60]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
