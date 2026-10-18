"""Find the JobStreet search parameters that actually return Indonesian postings."""

from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "application/json", "Accept-Language": "id-ID,id;q=0.9"}

TRIES = [
    ("id host, siteKey", "https://id.jobstreet.com/api/jobsearch/v5/search",
     {"siteKey": "ID-Main", "sourcesystem": "houston", "keywords": "developer", "page": 1}),
    ("id host, no siteKey", "https://id.jobstreet.com/api/jobsearch/v5/search",
     {"keywords": "developer", "page": 1}),
    ("co.id, where=Indonesia", "https://www.jobstreet.co.id/api/jobsearch/v5/search",
     {"siteKey": "ID-Main", "sourcesystem": "houston", "keywords": "developer", "where": "Indonesia", "page": 1}),
    ("co.id, locale", "https://www.jobstreet.co.id/api/jobsearch/v5/search",
     {"siteKey": "ID-Main", "sourcesystem": "houston", "keywords": "developer", "locale": "id-ID", "page": 1}),
    ("co.id, + pageSize", "https://www.jobstreet.co.id/api/jobsearch/v5/search",
     {"siteKey": "ID-Main", "sourcesystem": "houston", "keywords": "developer", "pageSize": 30, "page": 1}),
]


def main() -> int:
    for label, url, params in TRIES:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=25)
            payload = resp.json()
        except Exception as exc:
            print(f"ERR  {label:<24} {type(exc).__name__}: {str(exc)[:60]}")
            continue
        rows = payload.get("data") or []
        total = payload.get("totalCount")
        sample = "-"
        if rows:
            locations = rows[0].get("locations") or [{}]
            sample = f"{locations[0].get('countryCode', '?')} | {rows[0].get('title', '')[:40]}"
        print(f"{resp.status_code}  {label:<24} rows={len(rows):<3} total={total}  {sample}")
        if label == "co.id, + pageSize":
            print("  searchParams:", payload.get("searchParams"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
