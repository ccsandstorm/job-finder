"""Adzuna job search API: aggregates postings from Indeed-style job boards and employer sites.

Free key at https://developer.adzuna.com/ . Set ADZUNA_APP_ID and ADZUNA_APP_KEY.
"""
from __future__ import annotations

import os

from ..models import Job
from . import get_json, log, parse_date, strip_html

URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"


def parse(data: dict) -> list[Job]:
    jobs = []
    for j in data.get("results", []):
        loc = (j.get("location") or {}).get("display_name", "")
        contract = " ".join(filter(None, [j.get("contract_time"), j.get("contract_type")]))
        jobs.append(
            Job(
                source="Adzuna",
                title=strip_html(j.get("title")),
                company=(j.get("company") or {}).get("display_name", ""),
                locations=[loc] if loc else [],
                url=j.get("redirect_url", ""),
                description=strip_html(j.get("description")),
                posted=parse_date(j.get("created")),
                employment_type=contract.replace("part_time", "Part-time").replace("full_time", "Full-time"),
                remote="remote" in (j.get("title", "") + loc).lower(),
            )
        )
    return jobs


def fetch(cfg: dict) -> list[Job]:
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.info("adzuna: skipped (set ADZUNA_APP_ID and ADZUNA_APP_KEY to enable)")
        return []
    jobs: list[Job] = []
    for query in cfg.get("queries", []):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 50,
            "max_days_old": cfg.get("days", 14),
            "where": cfg.get("where", "San Francisco, CA"),
            "distance": cfg.get("distance_km", 60),
            **query,
        }
        for page in range(1, cfg.get("pages", 2) + 1):
            try:
                jobs += parse(get_json(URL.format(page=page), params=params))
            except Exception as exc:  # noqa: BLE001
                log.warning("adzuna %s page %d failed: %s", query, page, exc)
                break
    return jobs
