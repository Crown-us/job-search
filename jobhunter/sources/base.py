"""Shared HTTP plumbing for source adapters."""

from __future__ import annotations

import html
import json
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
    "jobstreet": 0,
    "kalibrr": 0,
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


_LDJSON = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)
_SEEK_BODY = re.compile(r'data-automation="jobAdDetails"(.*?)</section>', re.S)


def _jsonld_objects(page: str):
    for raw in _LDJSON.findall(page):
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            yield from data
        else:
            yield data


def extract_job_description(page: str) -> str:
    """Pull the ad body out of a job page.

    JSON-LD JobPosting first (clean, standard), then SEEK's rendered block.
    """
    for obj in _jsonld_objects(page):
        if not isinstance(obj, dict):
            continue
        kind = obj.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            description = obj.get("description")
            if description:
                return strip_html(description)

    block = _SEEK_BODY.search(page)
    if block:
        return strip_html(block.group(1))
    return ""

