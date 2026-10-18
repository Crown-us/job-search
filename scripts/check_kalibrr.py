"""Check Kalibrr pagination, keyword behaviour, and company diversity."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter.sources import kalibrr


def main() -> int:
    conn = sqlite3.connect("data/jobs.db")
    companies = conn.execute(
        "SELECT COUNT(DISTINCT company) FROM jobs WHERE source='kalibrr'"
    ).fetchone()[0]
    print("kalibrr distinct companies:", companies)
    for row in conn.execute(
        "SELECT company, COUNT(*) FROM jobs WHERE source='kalibrr' GROUP BY company ORDER BY 2 DESC LIMIT 5"
    ):
        print("  ", row)

    p1 = kalibrr.fetch("", page=1)
    p2 = kalibrr.fetch("", page=2)
    ids1 = [j.external_id for j in p1]
    ids2 = [j.external_id for j in p2]
    print("page1 == page2:", ids1 == ids2, "| overlap:", len(set(ids1) & set(ids2)))

    q = kalibrr.fetch("developer", page=1)
    print("p1 titles:  ", [j.title[:34] for j in p1[:3]])
    print("q=dev titles:", [j.title[:34] for j in q[:3]])
    print("company p1:", sorted({j.company for j in p1})[:8])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
