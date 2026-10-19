"""Jobicy remote jobs API. jobGeo tells where the candidate must live."""

from __future__ import annotations

from ..model import Job
from .base import get_json, strip_html


def fetch(token: str = "", full: bool = False) -> list[Job]:
    data = get_json("https://jobicy.com/api/v2/remote-jobs", count=50)
    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        geo = item.get("jobGeo") or "Remote"
        salary = ""
        low, high, currency = item.get("annualSalaryMin"), item.get("annualSalaryMax"), item.get("salaryCurrency")
        if low or high:
            salary = f"{currency or ''} {low or ''}-{high or ''}".strip()
        jobs.append(
            Job(
                source="jobicy",
                company=item.get("companyName", ""),
                title=item.get("jobTitle", ""),
                url=item.get("url", ""),
                location=geo,
                remote=True,
                salary=salary,
                department=" | ".join(
                    str(x) for x in (item.get("jobIndustry"), item.get("jobLevel")) if x
                ),
                description=strip_html(item.get("jobDescription") or item.get("jobExcerpt"))[:6000],
                posted_at=item.get("pubDate") or "",
                external_id=str(item.get("id", "")),
            )
        )
    return jobs
