"""Remotive public API: curated remote jobs, all with a required location field."""

from __future__ import annotations

from ..model import Job
from .base import get_json, strip_html


def fetch(token: str = "", full: bool = False) -> list[Job]:
    data = get_json("https://remotive.com/api/remote-jobs", limit=100)
    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        location = item.get("candidate_required_location") or "Remote"
        jobs.append(
            Job(
                source="remotive",
                company=item.get("company_name", ""),
                title=item.get("title", ""),
                url=item.get("url", ""),
                location=location,
                remote=True,
                salary=item.get("salary") or "",
                department=", ".join(item.get("tags") or []) or (item.get("category") or ""),
                description=strip_html(item.get("description"))[:6000],
                posted_at=item.get("publication_date") or "",
                external_id=str(item.get("id", "")),
            )
        )
    return jobs
