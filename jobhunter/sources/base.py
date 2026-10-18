"""Shared HTTP plumbing for source adapters."""

from __future__ import annotations

import html
import re

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})

# When the same posting shows up on several boards, keep the one from the
# earliest source in this list: ATS first, aggregators last.
SOURCE_PRIORITY = {
    "greenhouse": 0,
    "lever": 0,
    "ashby": 0,
    "workable": 0,
    "remoteok": 1,
    "hackernews": 2,
}

_TAG = re.compile(r"<[^>]+>")


def get_json(url: str, timeout: int = 25, **params):
    resp = SESSION.get(url, timeout=timeout, params=params or None)
    resp.raise_for_status()
    return resp.json()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG.sub(" ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def is_remote(location: str) -> bool:
    return bool(re.search(r"\b(remote|anywhere|distributed|wfh)\b", location or "", re.I))
