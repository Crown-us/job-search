"""Delete all rows from one source, so a bad adapter run can be undone cleanly.

Run: python scripts/purge_source.py kalibrr
"""

from __future__ import annotations

import sqlite3
import sys

SOURCE = sys.argv[1] if len(sys.argv) > 1 else ""

if not SOURCE:
    raise SystemExit("usage: python scripts/purge_source.py <source>")

conn = sqlite3.connect("data/jobs.db")
before = conn.execute("SELECT COUNT(*) FROM jobs WHERE source = ?", (SOURCE,)).fetchone()[0]
conn.execute("DELETE FROM jobs WHERE source = ?", (SOURCE,))
conn.commit()
after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
print(f"deleted {before} row(s) from source={SOURCE}; {after} remain")
