"""Lever postings API. Public per-company endpoint, JSON mode."""

from __future__ import annotations

from ..model import Job
from .base import get_json, is_remote, strip_html


def fetch(token: str, full: bool = False) -> list[Job]:
    data = get_json(f"https://api.lever.co/v0/postings/{token}", mode="json")
    if not isinstance(data, list):
        return []
    jobs: list[Job] = []
    for item in data:
        categories = item.get("categories") or {}
        location = categories.get("location") or ""
        jobs.append(
            Job(
                source="lever",
                company=token.replace("-", " ").title(),
                title=item.get("text", ""),
                url=item.get("hostedUrl", ""),
                location=location,
                remote=is_remote(location) or bool(item.get("workplaceType") == "remote"),
                department=categories.get("team") or categories.get("department") or "",
                description=strip_html(item.get("descriptionPlain") or item.get("description")) if full else "",
                posted_at=item.get("createdAt") or "",
                external_id=str(item.get("id", "")),
            )
        )
    return jobs
