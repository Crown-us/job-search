"""JobStreet Indonesia search API (SEEK-backed).

The .co.id host silently falls back to Australian results; id.jobstreet.com with
siteKey=ID-Main is the one that returns Indonesian postings.
"""

from __future__ import annotations

from ..model import Job
from .base import is_remote, strip_html

import requests

from .base import SESSION, extract_job_description

ENDPOINT = "https://id.jobstreet.com/api/jobsearch/v5/search"


def _is_remote(item: dict, location: str) -> bool:
    if is_remote(location):
        return True
    # workArrangements looks like {"data": [{"label": {"text": "On-site"}}]}
    blob = str(item.get("workArrangements") or "").lower()
    return "remote" in blob


def fetch(keyword: str, page: int = 1, full: bool = False) -> list[Job]:
    resp = SESSION.get(
        ENDPOINT,
        params={
            "siteKey": "ID-Main",
            "sourcesystem": "houston",
            "keywords": keyword,
            "page": page,
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    jobs: list[Job] = []
    for item in payload.get("data") or []:
        locations = item.get("locations") or [{}]
        location = locations[0].get("label") or ""
        classifications = item.get("classifications") or [{}]
        department = (classifications[0].get("classification") or {}).get("description") or ""
        sub = (classifications[0].get("subclassification") or {}).get("description") or ""
        company = item.get("companyName") or (item.get("advertiser") or {}).get("description") or ""
        job_id = str(item.get("id", ""))
        jobs.append(
            Job(
                source="jobstreet",
                company=company,
                title=item.get("title", ""),
                url=f"https://id.jobstreet.com/id/job/{job_id}",
                location=location,
                remote=_is_remote(item, location),
                salary=item.get("salaryLabel") or "",
                department=" | ".join(x for x in (department, sub) if x),
                description=strip_html(item.get("teaser")) if full else "",
                posted_at=item.get("listingDate") or "",
                external_id=job_id,
            )
        )
    return jobs


def fetch_detail(url: str) -> str:
    """Full JD text from the posting page (JSON-LD, fallback to the ad block)."""
    resp = SESSION.get(url, headers={"Accept": "text/html"}, timeout=30)
    resp.raise_for_status()
    return extract_job_description(resp.text)
