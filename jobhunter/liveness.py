"""Is a stored posting still open? Re-check the original page before it goes public.

A board keeps a posting in the database long after the employer closes it, so the
public site would link to "not found" pages. Each source signals a closed posting
differently; only those definite signals close a job. Blocks, timeouts and server
errors return "unknown" and leave the job as it was.
"""

from __future__ import annotations

import concurrent.futures as cf
import re
from datetime import datetime, timezone

from .sources.base import SESSION

OPEN, CLOSED, UNKNOWN = "open", "closed", "unknown"
PAGE_HEADERS = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "id,en;q=0.8"}


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _kalibrr(url: str, now: datetime) -> tuple[str, str]:
    # The job page is a JS shell; the API behind it carries the deadline and visibility.
    found = re.search(r"/jobs/(\d+)", url)
    if not found:
        return UNKNOWN, "no job id in url"
    resp = SESSION.get(f"https://www.kalibrr.com/api/jobs/{found.group(1)}", timeout=20)
    if resp.status_code in (404, 410):
        return CLOSED, f"api {resp.status_code}"
    if resp.status_code != 200:
        return UNKNOWN, f"api {resp.status_code}"
    data = resp.json()
    end = _when(data.get("application_end_date"))
    if end and end < now:
        return CLOSED, f"deadline {end:%Y-%m-%d}"
    if data.get("visibility") and data["visibility"] != "public":
        return CLOSED, f"visibility {data['visibility']}"
    return OPEN, "api ok"


def check(source: str, url: str, now: datetime | None = None) -> tuple[str, str]:
    """(state, reason) for one posting."""
    now = now or datetime.now(timezone.utc)
    if not url:
        return UNKNOWN, "no url"
    try:
        if source == "kalibrr":
            return _kalibrr(url, now)
        resp = SESSION.get(url, timeout=20, headers=PAGE_HEADERS, allow_redirects=True)
    except Exception as exc:  # network trouble says nothing about the posting
        return UNKNOWN, type(exc).__name__
    if resp.status_code in (404, 410):
        return CLOSED, f"http {resp.status_code}"
    if resp.status_code != 200:
        return UNKNOWN, f"http {resp.status_code}"
    if source == "greenhouse":
        # Closed Greenhouse jobs bounce to the board with ?error=true; company career
        # sites that wrap Greenhouse drop the job id from the final URL instead.
        job_id = re.search(r"(?:gh_jid=|/jobs/)(\d+)", url)
        if "error=true" in resp.url or (job_id and job_id.group(1) not in resp.url):
            return CLOSED, "redirected to board"
    if source == "jobstreet" and '"isExpired":true' in resp.text:
        return CLOSED, "isExpired"
    return OPEN, f"http {resp.status_code}"


def check_many(rows: list[dict], workers: int = 6) -> list[tuple[dict, str, str]]:
    now = datetime.now(timezone.utc)
    with cf.ThreadPoolExecutor(workers) as pool:
        results = pool.map(lambda r: check(r["source"], r["url"], now), rows)
        return [(row, state, reason) for row, (state, reason) in zip(rows, results)]
