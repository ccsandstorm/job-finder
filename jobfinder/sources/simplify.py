"""SimplifyJobs community internship and new-grad lists on GitHub (public, MIT licensed).

These lists aggregate internships from company career pages, so they cover most
of what you'd find on LinkedIn or Handshake for tech internships.
"""
from __future__ import annotations

from ..models import Job
from . import get_json, log, parse_date

LISTS = {
    "internships": "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
    "new_grad": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
}


def parse(data: list[dict], list_name: str = "internships") -> list[Job]:
    jobs = []
    for item in data:
        if not item.get("active") or not item.get("is_visible", True):
            continue
        degrees = item.get("degrees") or []
        if degrees and "Bachelor's" not in degrees:
            continue  # grad-school-only roles
        locations = item.get("locations") or []
        jobs.append(
            Job(
                source=f"Simplify ({list_name})",
                title=item.get("title", "").strip(),
                company=item.get("company_name", "").strip(),
                locations=locations,
                url=item.get("url", ""),
                description=item.get("category", "") or "",
                posted=parse_date(item.get("date_posted")),
                employment_type="Intern" if list_name == "internships" else "Full-time",
                terms=[t for t in item.get("terms") or [] if t != "N/A"],
                remote=any("remote" in loc.lower() for loc in locations),
                extra={"category": item.get("category"), "sponsorship": item.get("sponsorship")},
            )
        )
    return jobs


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for name in cfg.get("lists", ["internships"]):
        url = LISTS.get(name)
        if not url:
            log.warning("simplify: unknown list %s", name)
            continue
        try:
            jobs += parse(get_json(url), name)
        except Exception as exc:  # noqa: BLE001 - one bad source must not stop the run
            log.warning("simplify %s failed: %s", name, exc)
    return jobs
