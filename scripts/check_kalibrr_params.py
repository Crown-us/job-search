"""Try parameter names that might turn the Kalibrr feed into a real search."""

from __future__ import annotations

import requests

URL = "https://www.kalibrr.com/kjs/job_board/search"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

VARIANTS = [
    ("baseline", {}),
    ("search_text", {"search_text": "developer"}),
    ("text", {"text": "developer"}),
    ("q", {"q": "developer"}),
    ("keyword", {"keyword": "developer"}),
    ("search", {"search": "developer"}),
    ("function=Engineering", {"function": "Engineering"}),
    ("tenure=Full time", {"tenure": "Full time"}),
]


def main() -> int:
    for label, extra in VARIANTS:
        params = {"limit": 8, "offset": 0, **extra}
        try:
            payload = requests.get(URL, params=params, headers=HEADERS, timeout=25).json()
            rows = payload.get("jobs") or []
            companies = sorted({(r.get("company_name") or "?") for r in rows})
            titles = [r.get("name", "")[:30] for r in rows[:2]]
            print(f"{label:<22} n={len(rows):<3} companies={companies[:4]} titles={titles}")
        except Exception as exc:
            print(f"{label:<22} ERR {type(exc).__name__}: {str(exc)[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
