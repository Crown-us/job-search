"""Explain exactly which filter rejects each stored posting.

Run: python scripts/why_filtered.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db
from jobhunter.pipeline import _posted_within
from jobhunter.model import Job


def reason(job: Job, flt: dict) -> str | None:
    title = (job.title or "").lower()
    for keyword in flt.get("exclude_title_keywords") or []:
        if str(keyword).lower() in title:
            return f"judul mengandung '{keyword}'"

    company = (job.company or "").strip()
    if flt.get("require_company_name", True) and (not company or company.lower() == "unknown"):
        return "nama perusahaan kosong"
    for keyword in flt.get("exclude_company_keywords") or []:
        if str(keyword).lower() in company.lower():
            return f"perusahaan mengandung '{keyword}'"

    allowed = [str(k).lower() for k in flt.get("location_allow") or []]
    if allowed and not job.remote:
        location = (job.location or "").lower()
        if location and not any(k in location for k in allowed):
            return f"lokasi '{job.location}' di luar daftar"

    if flt.get("remote_only") and not job.remote:
        return "bukan remote"

    if not _posted_within(job.posted_at, int(flt.get("max_age_days") or 0)):
        return f"posting lebih tua dari {flt.get('max_age_days')} hari ({job.posted_at[:10]})"
    return None


def main() -> int:
    flt = config.filters()
    conn = db.connect()
    rows = [dict(r) for r in conn.execute("SELECT * FROM jobs")]
    count = 0
    for row in rows:
        job = Job(
            source=row["source"], company=row["company"], title=row["title"], url=row["url"],
            location=row["location"] or "", remote=bool(row["remote"]), salary=row["salary"] or "",
            department=row["department"] or "", description=row["description"] or "",
            posted_at=row["posted_at"] or "",
        )
        why = reason(job, flt)
        if why:
            count += 1
            print(f"  {row['company'][:26]:<28} {row['title'][:40]:<42} -> {why}")
    print(f"\n{count} dari {len(rows)} lowongan ditolak filter")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
