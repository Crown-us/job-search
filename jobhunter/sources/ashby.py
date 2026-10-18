"""Ashby public job board API."""

from __future__ import annotations

from ..model import Job
from .base import get_json, is_remote, strip_html


def fetch(token: str, full: bool = False) -> list[Job]:
    data = get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{token}",
        includeCompensation="true",
    )
    jobs: list[Job] = []
    for item in data.get("jobs", []):
        location = item.get("location") or ""
        salary = ""
        comp = item.get("compensation") or {}
        if isinstance(comp, dict):
            summary = comp.get("compensationTierSummary")
            salary = summary if isinstance(summary, str) else ""
        jobs.append(
            Job(
                source="ashby",
                company=token.replace("-", " ").title(),
                title=item.get("title", ""),
                url=item.get("jobUrl", ""),
                location=location,
                remote=bool(item.get("isRemote")) or is_remote(location),
                department=item.get("department") or "",
                description=strip_html(item.get("descriptionPlain")) if full else "",
                posted_at=item.get("publishedAt") or "",
                salary=salary,
                external_id=str(item.get("id", "")),
            )
        )
    return jobs
