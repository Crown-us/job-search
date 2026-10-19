"""List postings whose company name looks anonymous or missing."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PATTERNS = (
    "private advertiser",
    "confidential",
    "anonymous",
    "undisclosed",
    "unknown",
    "tanpa nama",
    "perusahaan rahasia",
)

conn = sqlite3.connect("data/jobs.db")
conn.row_factory = sqlite3.Row

print("semua company unik (top 15 by count):")
for row in conn.execute(
    "SELECT company, COUNT(*) c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 15"
):
    print(f"  {row['company'][:44]:<46} {row['c']}")

print("\nkandidat anonim:")
total = 0
for row in conn.execute(
    "SELECT id, company, title, source, score FROM jobs ORDER BY score DESC"
):
    company = (row["company"] or "").strip().lower()
    if not company or any(p in company for p in PATTERNS):
        total += 1
        print(f"  {row['id'][:8]}  {row['company'][:30]:<32} {row['title'][:44]:<46} {row['source']}")

print(f"\ntotal kandidat: {total} dari {conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]}")
conn.close()
