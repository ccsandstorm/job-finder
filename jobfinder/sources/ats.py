"""Public job-board APIs that companies use for their own careers pages.

Greenhouse, Lever, and Ashby publish every open role as JSON with no key needed.
Add company "slugs" (the name in the careers-page URL) in config/companies.yaml.
"""
from __future__ import annotations

from ..models import Job
from . import get_json, log, parse_date, strip_html


def parse_greenhouse(data: dict, company: str) -> list[Job]:
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        jobs.append(
            Job(
                source="Greenhouse",
                title=j.get("title", "").strip(),
                company=company,
                locations=[loc] if loc else [],
                url=j.get("absolute_url", ""),
                description=strip_html(j.get("content")),
                posted=parse_date(j.get("first_published") or j.get("updated_at")),
                remote="remote" in loc.lower(),
            )
        )
    return jobs


def parse_lever(data: list[dict], company: str) -> list[Job]:
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        locs = cats.get("allLocations") or ([cats["location"]] if cats.get("location") else [])
        jobs.append(
            Job(
                source="Lever",
                title=j.get("text", "").strip(),
                company=company,
                locations=locs,
                url=j.get("hostedUrl", ""),
                description=j.get("descriptionPlain", "") or strip_html(j.get("description")),
                posted=parse_date(j.get("createdAt")),
                employment_type=cats.get("commitment", "") or "",
                remote=j.get("workplaceType") == "remote" or any("remote" in l.lower() for l in locs),
            )
        )
    return jobs


def parse_ashby(data: dict, company: str) -> list[Job]:
    jobs = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location")] if j.get("location") else []
        locs += [s.get("location") for s in j.get("secondaryLocations") or [] if s.get("location")]
        jobs.append(
            Job(
                source="Ashby",
                title=j.get("title", "").strip(),
                company=company,
                locations=locs,
                url=j.get("jobUrl", ""),
                description=j.get("descriptionPlain", "") or strip_html(j.get("descriptionHtml")),
                posted=parse_date(j.get("publishedAt")),
                employment_type=(j.get("employmentType") or "").replace("PartTime", "Part-time")
                .replace("FullTime", "Full-time"),
                remote=bool(j.get("isRemote")),
            )
        )
    return jobs


def _name(entry) -> tuple[str, str]:
    """Entries are either 'slug' or {'slug': ..., 'name': ...}."""
    if isinstance(entry, dict):
        return entry["slug"], entry.get("name", entry["slug"])
    return entry, entry.replace("-", " ").title()


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    boards = [
        ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true", parse_greenhouse),
        ("lever", "https://api.lever.co/v0/postings/{}?mode=json", parse_lever),
        ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{}", parse_ashby),
    ]
    for kind, url, parser in boards:
        for entry in cfg.get(kind) or []:
            slug, name = _name(entry)
            try:
                jobs += parser(get_json(url.format(slug)), name)
            except Exception as exc:  # noqa: BLE001
                log.warning("%s/%s failed: %s", kind, slug, exc)
    return jobs
