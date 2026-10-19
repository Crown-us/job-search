"""Fit distribution and the current best matches."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db


def main() -> int:
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    analyzed = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    with_jd = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE length(description) > 300"
    ).fetchone()[0]
    print(f"posting={total}  punya JD={with_jd}  sudah dianalisis={analyzed}")

    print("\ndistribusi fit:")
    for label, low, high in (
        (">= 80  kuat", 80, 101),
        ("70-79 layak", 70, 80),
        ("60-69 marginal", 60, 70),
        ("< 60  lemah", 0, 60),
    ):
        count = conn.execute(
            "SELECT COUNT(*) FROM analyses WHERE fit >= ? AND fit < ?", (low, high)
        ).fetchone()[0]
        print(f"  {label:<16} {count}")

    print("\ntop 10:")
    rows = conn.execute(
        """
        SELECT a.fit, j.company, j.title, j.location, a.gaps
        FROM analyses a JOIN jobs j ON j.id = a.job_id
        ORDER BY a.fit DESC LIMIT 10
        """
    ).fetchall()
    for fit, company, title, location, gaps in rows:
        gap = (gaps or "").split("\n")[0][:44]
        print(f"  {fit:>3}  {company[:24]:<26} {title[:40]:<42} {gap}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
