"""Hacker News "Who is hiring?" monthly thread, via the free Algolia API."""

from __future__ import annotations

import re

from ..model import Job
from .base import get_json, strip_html

_SPLIT = re.compile(r"\s*(?:\||–|—| - )\s*")


def fetch(token: str = "", full: bool = False, limit: int = 120) -> list[Job]:
    hits = get_json(
        "https://hn.algolia.com/api/v1/search_by_date",
        query="Ask HN: Who is hiring?",
        tags="story",
        hitsPerPage=6,
    ).get("hits", [])
    if not hits:
        return []
    story = max(hits, key=lambda h: h.get("created_at_i") or 0)
    thread = get_json(f"https://hn.algolia.com/api/v1/items/{story['objectID']}")
    posted = str(story.get("created_at") or "")

    jobs: list[Job] = []
    for child in (thread.get("children") or [])[:limit]:
        text = strip_html(child.get("text"))
        if len(text) < 30:
            continue
        head = text.split(". ")[0][:220]
        parts = [p.strip() for p in _SPLIT.split(head) if p.strip()]
        company = parts[0] if parts else "HN"
        title = parts[1] if len(parts) > 2 else (parts[0] if parts else "")
        location = next(
            (p for p in parts[1:] if re.search(r"remote|onsite|hybrid|indonesia|asia|apac", p, re.I)),
            "",
        )
        jobs.append(
            Job(
                source="hackernews",
                company=company,
                title=title,
                url=f"https://news.ycombinator.com/item?id={child.get('id')}",
                location=location,
                remote=bool(re.search(r"remote", location, re.I)),
                description=text[:2000] if full else "",
                posted_at=posted,
                external_id=str(child.get("id")),
            )
        )
    return jobs
