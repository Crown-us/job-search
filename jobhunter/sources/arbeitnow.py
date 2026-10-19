"""Arbeitnow job board API.

Mostly German on-site roles; only entries flagged remote are worth keeping, and
filters.yaml drops the rest by location.
"""

from __future__ import annotations

from ..model import Job
from .base import get_json, strip_html


def fetch(token: str = "", full: bool = False) -> list[Job]:
    data = get_json("https://www.arbeitnow.com/api/job-board-api")
    jobs: list[Job] = []
    for item in data.get("data") or []:
        jobs.append(
            Job(
                source="arbeitnow",
                company=item.get("company_name", ""),
                title=item.get("title", ""),
                url=item.get("url", ""),
                location=item.get("location") or "",
                remote=bool(item.get("remote")),
                department=", ".join(item.get("job_types") or []),
                description=strip_html(item.get("description"))[:6000],
                posted_at=item.get("created_at") or "",
                external_id=str(item.get("slug", "")),
            )
        )
    return jobs
