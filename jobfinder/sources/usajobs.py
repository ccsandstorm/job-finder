"""USAJOBS public search API (federal jobs, including Pathways student internships).

Needs a free API key from https://developer.usajobs.gov/apirequest/
Set USAJOBS_API_KEY and USAJOBS_EMAIL as environment variables (or GitHub secrets).
"""
from __future__ import annotations

import os

from ..models import Job
from . import get_json, log, parse_date, strip_html

URL = "https://data.usajobs.gov/api/search"


def parse(data: dict) -> list[Job]:
    jobs = []
    items = (data.get("SearchResult") or {}).get("SearchResultItems") or []
    for item in items:
        d = item.get("MatchedObjectDescriptor") or {}
        details = ((d.get("UserArea") or {}).get("Details")) or {}
        schedule = ", ".join(s.get("Name", "") for s in d.get("PositionSchedule") or [])
        locs = [l.get("LocationName", "") for l in d.get("PositionLocation") or []] or [
            d.get("PositionLocationDisplay", "")
        ]
        title = d.get("PositionTitle", "")
        hiring_paths = details.get("HiringPath") or []
        jobs.append(
            Job(
                source="USAJOBS",
                title=title,
                company=d.get("OrganizationName") or d.get("DepartmentName", ""),
                locations=[l for l in locs if l],
                url=d.get("PositionURI", ""),
                description=strip_html(
                    " ".join(
                        filter(None, [details.get("JobSummary"), d.get("QualificationSummary")])
                    )
                ),
                posted=parse_date(d.get("PublicationStartDate")),
                closes=parse_date(d.get("ApplicationCloseDate")),
                employment_type="Intern" if "student" in hiring_paths or "intern" in title.lower() else schedule,
                remote=any("anywhere" in l.lower() or "remote" in l.lower() for l in locs),
                extra={
                    "hiring_paths": hiring_paths,
                    "veterans": "vet" in hiring_paths,
                    "security_clearance": details.get("SecurityClearance"),
                },
            )
        )
    return jobs


def fetch(cfg: dict) -> list[Job]:
    key, email = os.getenv("USAJOBS_API_KEY"), os.getenv("USAJOBS_EMAIL")
    if not key or not email:
        log.info("usajobs: skipped (set USAJOBS_API_KEY and USAJOBS_EMAIL to enable)")
        return []
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    jobs: list[Job] = []
    for query in cfg.get("queries", []):
        params = {"ResultsPerPage": 250, "DatePosted": cfg.get("days", 30), **query}
        try:
            jobs += parse(get_json(URL, headers=headers, params=params))
        except Exception as exc:  # noqa: BLE001
            log.warning("usajobs %s failed: %s", query, exc)
    return jobs
