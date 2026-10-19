"""Himalayas remote jobs API. Includes salary range and location restrictions."""

from __future__ import annotations

from ..model import Job
from .base import get_json, strip_html


def _restrictions(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v) or "Remote"
    return str(value or "Remote")


def fetch(token: str = "", full: bool = False) -> list[Job]:
    data = get_json("https://himalayas.app/jobs/api", limit=50)
    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        salary = ""
        low, high, currency = item.get("minSalary"), item.get("maxSalary"), item.get("currency")
        if low or high:
            salary = f"{currency or ''} {low or ''}-{high or ''}".strip()
        url = item.get("applicationLink") or item.get("guid") or ""
        jobs.append(
            Job(
                source="himalayas",
                company=item.get("companyName", ""),
                title=item.get("title", ""),
                url=url,
                location=_restrictions(item.get("locationRestrictions")),
                remote=True,
                salary=salary,
                department=" | ".join(
                    str(x) for x in (item.get("employmentType"), item.get("seniority")) if x
                ),
                description=strip_html(item.get("description") or item.get("excerpt"))[:6000],
                posted_at=item.get("pubDate") or "",
                external_id=str(item.get("guid") or url),
            )
        )
    return jobs
