"""Source registry. Every adapter exposes fetch(...) -> list[Job]."""

from __future__ import annotations

from . import (
    arbeitnow,
    ashby,
    greenhouse,
    hackernews,
    himalayas,
    jobicy,
    jobstreet,
    kalibrr,
    lever,
    remoteok,
    remotive,
    workable,
)

ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "workable": workable.fetch,
    "remoteok": remoteok.fetch,
    "remotive": remotive.fetch,
    "jobicy": jobicy.fetch,
    "himalayas": himalayas.fetch,
    "arbeitnow": arbeitnow.fetch,
    "hackernews": hackernews.fetch,
    "jobstreet": jobstreet.fetch,
    "kalibrr": kalibrr.fetch,
}

# Sources that need a company token from companies.yaml.
BOARD_SOURCES = {"greenhouse", "lever", "ashby", "workable"}

# Sources that publish one global feed, enabled through companies.yaml `feeds`.
FEED_SOURCES = {"remoteok", "remotive", "jobicy", "himalayas", "arbeitnow", "hackernews"}

# Sources searched by keyword from searches.yaml.
QUERY_SOURCES = {"jobstreet", "kalibrr"}
