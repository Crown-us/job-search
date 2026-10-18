"""Probe Indonesian job boards for a public JSON endpoint worth adapting.

Run: python scripts/probe_sources.py
Prints HTTP status, content type and a snippet for each candidate. Anything that
returns JSON with job objects is a candidate for a real adapter.
"""

from __future__ import annotations

import json
import sys

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

CANDIDATES = [
    ("glints (v1)", "https://glints.com/api/v1/job-posts?limit=5"),
    ("glints (search)", "https://glints.com/api/v1/job-posts/search?limit=5&keyword=developer"),
    ("glints (api host)", "https://api.glints.com/v1/job-posts?limit=5"),
    ("jobstreet (v5)", "https://www.jobstreet.co.id/api/jobsearch/v5/search?siteKey=ID-Main&sourcesystem=houston&keywords=developer&page=1"),
    ("jobstreet (v4)", "https://www.jobstreet.co.id/api/jobsearch/v4/search?siteKey=ID-Main&sourcesystem=houston&keywords=developer&page=1"),
    ("kalibrr", "https://www.kalibrr.com/kjs/job_board/search?limit=5&offset=0"),
    ("kalibrr (api)", "https://api.kalibrr.com/v1/job_board/search?limit=5"),
    ("dealls", "https://api.dealls.id/v1/jobs?limit=5"),
    ("dealls (web)", "https://dealls.com/api/v1/jobs?limit=5"),
    ("karir", "https://api.karir.com/v1/jobs?limit=5"),
    ("loker.id", "https://loker.id/api/jobs?limit=5"),
    ("remotive", "https://remotive.com/api/remote-jobs?limit=5"),
    ("arbeitnow", "https://www.arbeitnow.com/api/job-board-api"),
    ("jobicy", "https://jobicy.com/api/v2/remote-jobs?count=5"),
    ("himalayas", "https://himalayas.app/jobs/api?limit=5"),
    ("weworkremotely rss", "https://weworkremotely.com/categories/remote-programming-jobs.rss"),
]


def looks_like_jobs(payload) -> str:
    if isinstance(payload, dict):
        for key in ("jobs", "data", "results", "jobPosts", "items", "hits"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                return f"list under '{key}' ({len(value)})"
        return "dict keys: " + ", ".join(list(payload)[:8])
    if isinstance(payload, list):
        return f"list ({len(payload)})"
    return type(payload).__name__


def main() -> int:
    for name, url in CANDIDATES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            ctype = resp.headers.get("content-type", "")[:40]
            if "json" in ctype:
                try:
                    detail = looks_like_jobs(resp.json())
                except json.JSONDecodeError:
                    detail = "invalid json"
            elif "xml" in ctype or "rss" in ctype:
                detail = f"xml/rss {len(resp.text)} chars"
            else:
                detail = resp.text[:80].replace("\n", " ")
            print(f"{resp.status_code}  {name:<20} {ctype:<40} {detail}")
        except Exception as exc:
            print(f"ERR {name:<20} {type(exc).__name__}: {str(exc)[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
