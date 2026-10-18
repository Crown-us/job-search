"""Workable public widget API."""

from __future__ import annotations

from ..model import Job
from .base import get_json, is_remote, strip_html


def fetch(token: str, full: bool = False) -> list[Job]:
    data = get_json(
        f"https://apply.workable.com/api/v1/widget/accounts/{token}",
        details="true",
    )
    jobs: list[Job] = []
    for item in data.get("jobs", []):
        loc = item.get("location") or {}
        if isinstance(loc, dict):
            location = ", ".join(
                str(x) for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x
            )
        else:
            location = str(loc)
        jobs.append(
            Job(
                source="workable",
                company=item.get("company") or token.replace("-", " ").title(),
                title=item.get("title", ""),
                url=item.get("url") or item.get("shortlink") or "",
                location=location,
                remote=bool(item.get("telecommuting")) or is_remote(location),
                department=item.get("department") or "",
                description=strip_html(item.get("description")) if full else "",
                posted_at=item.get("published_on") or "",
                external_id=str(item.get("shortcode", "")),
            )
        )
    return jobs
