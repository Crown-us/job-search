"""Probe free remote-job APIs and print the fields we would map."""

from __future__ import annotations

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

CANDIDATES = [
    ("remotive", "https://remotive.com/api/remote-jobs?limit=3"),
    ("arbeitnow", "https://www.arbeitnow.com/api/job-board-api"),
    ("jobicy", "https://jobicy.com/api/v2/remote-jobs?count=3"),
    ("himalayas", "https://himalayas.app/jobs/api?limit=3"),
    ("remoteok", "https://remoteok.com/api"),
]


def main() -> int:
    for name, url in CANDIDATES:
        try:
            resp = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=25)
            payload = resp.json()
        except Exception as exc:
            print(f"{name:<10} ERR {type(exc).__name__}: {str(exc)[:60]}")
            continue

        if isinstance(payload, dict):
            key = next((k for k in ("jobs", "data", "results") if isinstance(payload.get(k), list)), None)
            items = payload.get(key) or []
            print(f"{name:<10} status={resp.status_code} root={list(payload)[:6]} list='{key}' n={len(items)}")
        else:
            items = [i for i in payload if isinstance(i, dict)]
            print(f"{name:<10} status={resp.status_code} list n={len(items)}")

        if items:
            first = items[1] if name == "remoteok" and len(items) > 1 else items[0]
            print("   keys:", sorted(first)[:18])
            for field in ("title", "position", "jobTitle", "name", "company_name", "companyName",
                          "location", "candidate_required_location", "jobGeo", "remote"):
                if field in first:
                    print(f"   {field}: {str(first[field])[:70]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
