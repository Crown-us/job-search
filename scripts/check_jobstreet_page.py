"""Locate the server-rendered JD block on a SEEK/JobStreet page."""

from __future__ import annotations

import re
import sqlite3

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def main() -> int:
    conn = sqlite3.connect("data/jobs.db")
    url = conn.execute(
        "SELECT url FROM jobs WHERE source='jobstreet' ORDER BY score DESC LIMIT 1"
    ).fetchone()[0]
    html = requests.get(url, headers={"User-Agent": UA}, timeout=30).text

    scripts = re.findall(r"<script([^>]*)>", html)
    print(f"{len(scripts)} script tags; first 12 attrs:")
    for attrs in scripts[:12]:
        print("  ", attrs.strip()[:110])

    print("\nmarks:")
    for marker in ("__NEXT_DATA__", "SEEK_REDUX", "__INITIAL_STATE__", "application/ld+json", "data-automation"):
        print(f"  {marker}: {html.count(marker)}")

    for match in list(re.finditer(r"description", html, re.I))[:3]:
        start = max(0, match.start() - 120)
        print("\n...context:", html[start: match.start() + 200].replace("\n", " ")[:320])

    # SEEK usually renders the ad body inside a section with data-automation="jobAdDetails"
    body = re.search(r'data-automation="jobAdDetails"(.*?)</section>', html, re.S)
    print("\njobAdDetails block found:", bool(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
