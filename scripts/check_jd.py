"""How much JD text do we actually have, and where can we get the rest?"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def db_report() -> None:
    conn = sqlite3.connect("data/jobs.db")
    print("description length by source:")
    for source, total, with_jd, avg in conn.execute(
        "SELECT source, COUNT(*), SUM(CASE WHEN length(description) > 300 THEN 1 ELSE 0 END), "
        "CAST(AVG(length(description)) AS INT) FROM jobs GROUP BY source ORDER BY 2 DESC"
    ):
        print(f"  {source:<12} total={total:<4} with_jd={with_jd:<4} avg_chars={avg}")


def probe_jobstreet_detail() -> None:
    conn = sqlite3.connect("data/jobs.db")
    row = conn.execute(
        "SELECT id, url, title FROM jobs WHERE source='jobstreet' ORDER BY score DESC LIMIT 1"
    ).fetchone()
    if not row:
        print("no jobstreet rows")
        return
    job_id, url, title = row
    print(f"\nprobe jobstreet detail for: {title[:50]}  ({job_id})")

    candidates = [
        f"https://id.jobstreet.com/api/jobsearch/v5/jobs/{job_id}",
        f"https://id.jobstreet.com/api/jobsearch/v5/job/{job_id}",
        f"https://id.jobstreet.com/api/jobs/v1/jobs/{job_id}",
        url,
    ]
    for target in candidates:
        try:
            resp = requests.get(target, headers={"User-Agent": UA, "Accept": "application/json, text/html"}, timeout=30)
            ctype = resp.headers.get("content-type", "")[:30]
            note = ""
            if "json" in ctype:
                try:
                    payload = resp.json()
                    keys = list(payload) if isinstance(payload, dict) else f"list[{len(payload)}]"
                    note = f"keys={keys}"
                except json.JSONDecodeError:
                    note = "invalid json"
            else:
                text = resp.text
                note = f"html {len(text)} chars, json-ld={'JobPosting' in text}"
            print(f"  {resp.status_code} {ctype:<30} {target[:70]}  {note}")
        except Exception as exc:
            print(f"  ERR {target[:70]}  {type(exc).__name__}")


if __name__ == "__main__":
    db_report()
    probe_jobstreet_detail()
