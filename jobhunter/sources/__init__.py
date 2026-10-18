"""Source registry. Every adapter exposes fetch(...) -> list[Job]."""

from __future__ import annotations

from . import ashby, greenhouse, hackernews, jobstreet, kalibrr, lever, remoteok, workable

ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "workable": workable.fetch,
    "remoteok": remoteok.fetch,
    "hackernews": hackernews.fetch,
    "jobstreet": jobstreet.fetch,
    "kalibrr": kalibrr.fetch,
}

# Sources that need a company token from companies.yaml.
BOARD_SOURCES = {"greenhouse", "lever", "ashby", "workable"}

# Sources that publish one global feed.
FEED_SOURCES = {"remoteok", "hackernews"}

# Sources searched by keyword from searches.yaml.
QUERY_SOURCES = {"jobstreet", "kalibrr"}
