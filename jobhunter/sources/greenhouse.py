"""Greenhouse public job board API. 731 jobs on stripe alone, no auth, no scraping."""

from __future__ import annotations

from ..model import Job
from .base import get_json, is_remote, strip_html


def fetch(token: str, full: bool = False) -> list[Job]:
    data = get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        content="true" if full else "false",
    )
    jobs: list[Job] = []
    for item in data.get("jobs", []):
        location = (item.get("location") or {}).get("name", "")
        departments = ", ".join(
            d.get("name", "") for d in item.get("departments", []) if d.get("name")
        )
        jobs.append(
            Job(
                source="greenhouse",
                company=item.get("company_name") or token,
                title=item.get("title", ""),
                url=item.get("absolute_url", ""),
                location=location,
                remote=is_remote(location),
                department=departments,
                description=strip_html(item.get("content")) if full else "",
                posted_at=item.get("updated_at") or item.get("first_published") or "",
                external_id=str(item.get("id", "")),
            )
        )
    return jobs
