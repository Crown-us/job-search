"""Inspect delivery state: how many were sent, how many remain eligible."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db


def main() -> int:
    conn = db.connect()
    sent = conn.execute("SELECT COUNT(*) FROM deliveries WHERE channel='discord'").fetchone()[0]
    total = conn.execute(
        "SELECT COUNT(*) FROM jobs j LEFT JOIN analyses a ON a.job_id=j.id "
        "WHERE j.status IN ('new','shortlist') AND COALESCE(a.fit,j.score,0) >= 65"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM jobs j LEFT JOIN analyses a ON a.job_id=j.id "
        "WHERE j.status IN ('new','shortlist') AND COALESCE(a.fit,j.score,0) >= 65 "
        "AND j.id NOT IN (SELECT job_id FROM deliveries WHERE channel='discord')"
    ).fetchone()[0]
    print(f"terkirim={sent}  eligible(>=65)={total}  sisa={pending}")
    for row in conn.execute(
        "SELECT d.sent_at, j.title FROM deliveries d JOIN jobs j ON j.id=d.job_id "
        "ORDER BY d.sent_at DESC LIMIT 4"
    ):
        print(f"  {row[0]}  {row[1][:52]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
