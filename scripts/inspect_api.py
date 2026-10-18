"""Inspect the shape of a JSON job API before writing an adapter.

Run: python scripts/inspect_api.py <url> [list-key]
"""

from __future__ import annotations

import json
import sys

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main(argv: list[str]) -> int:
    url = argv[0]
    key = argv[1] if len(argv) > 1 else None
    resp = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=25)
    payload = resp.json()

    print("top-level keys:", list(payload) if isinstance(payload, dict) else f"list[{len(payload)}]")
    items = payload
    if key and isinstance(payload, dict):
        items = payload.get(key) or []
    elif isinstance(payload, dict):
        for candidate in ("data", "jobs", "results"):
            if isinstance(payload.get(candidate), list):
                items = payload[candidate]
                break

    print(f"items: {len(items)}")
    if items:
        print(json.dumps(items[0], indent=1, ensure_ascii=False)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
