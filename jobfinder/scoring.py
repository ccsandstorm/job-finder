"""Sort each job into a track and score it 0-100 against the profile in config/profile.yaml."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .models import Job

INTERN_RE = re.compile(r"\b(intern|internship|co-?op|apprentice)\b", re.I)
PART_TIME_RE = re.compile(r"\bpart[- ]?time\b", re.I)
TERM_RE = re.compile(r"\b(summer|fall|winter|spring)\s*'?(20)?(\d{2})\b", re.I)


def _kw_regex(words: list[str]) -> re.Pattern | None:
    words = [w.strip() for w in words if w.strip()]
    if not words:
        return None
    # Whole-word match. A trailing * allows a prefix match: "data scien*" matches
    # "data science" and "data scientist". Lookarounds (not \b) so "C++" and "C#" work.
    parts = [re.escape(w[:-1]) if w.endswith("*") else re.escape(w) + r"(?![a-z0-9])" for w in words]
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(parts) + ")", re.I)


class Scorer:
    def __init__(self, profile: dict, now: datetime | None = None):
        self.p = profile
        self.now = now or datetime.now(timezone.utc)
        self.roles = {
            name: (_kw_regex(g["keywords"]), g.get("weight", 1.0))
            for name, g in profile.get("roles", {}).items()
        }
        self.skills = [(s, _kw_regex([s])) for s in profile.get("skills", [])]
        self.bonus = _kw_regex(profile.get("bonus_keywords", []))
        self.exclude = _kw_regex(profile.get("exclude_title", []))
        loc = profile.get("locations", {})
        self.loc_primary = _kw_regex(loc.get("primary", []))
        self.loc_nearby = _kw_regex(loc.get("nearby", []))
        self.loc_ok = _kw_regex(loc.get("acceptable", []))
        self.remote_ok = loc.get("remote_ok", True)
        self.non_us = _kw_regex(loc.get("non_us", []))
        t = profile.get("tracks", {})
        self.summer_terms = {s.lower() for s in t.get("summer_terms", ["Summer 2027"])}
        self.now_terms = {s.lower() for s in t.get("now_terms", [])}

    # ---------- track ----------
    def classify(self, job: Job) -> str:
        title = job.title
        etype = job.employment_type.lower()
        is_intern = bool(INTERN_RE.search(title)) or "intern" in etype
        terms = {t.lower() for t in job.terms}
        # Terms mentioned in the title, e.g. "Software Intern (Summer 2027)"
        for season, _, yy in TERM_RE.findall(title):
            terms.add(f"{season.lower()} 20{yy}")

        if is_intern:
            if terms & self.summer_terms:
                return "summer_2027"
            if terms & self.now_terms:
                return "part_time_now"  # fall/winter/spring internships fit around classes
            if terms:
                return "skip"  # only past or far-future terms
            return "summer_2027"
        if "part" in etype or PART_TIME_RE.search(title) or PART_TIME_RE.search(job.description[:600]):
            return "part_time_now"
        return "full_time"

    # ---------- location ----------
    def location_score(self, job: Job) -> tuple[float, str]:
        text = " ".join(job.locations)
        if self.loc_primary and self.loc_primary.search(text):
            return 1.0, "in San Francisco"
        if self.loc_nearby and self.loc_nearby.search(text):
            return 0.9, "in the Bay Area"
        if job.remote and self.remote_ok:
            if self.non_us and self.non_us.search(text) and not re.search(r"\b(US|USA|United States)\b", text):
                return 0.1, "remote outside the US"
            return 0.8, "remote"
        if self.loc_ok and self.loc_ok.search(text):
            return 0.4, "elsewhere in California"
        if not text.strip():
            return 0.3, "location not listed"
        return 0.1, "outside the Bay Area"

    # ---------- score ----------
    def score(self, job: Job) -> Job:
        job.track = self.classify(job)
        if job.track == "skip":
            return job
        if self.exclude and self.exclude.search(job.title):
            job.track = "skip"
            return job

        reasons: list[str] = []
        # Role fit (40): title match counts fully, description-only match counts half
        best, best_name = 0.0, ""
        for name, (rx, weight) in self.roles.items():
            if not rx:
                continue
            if rx.search(job.title):
                val = weight
            elif rx.search(job.description[:3000]):
                val = weight * 0.5
            else:
                continue
            if val > best:
                best, best_name = val, name
        if best == 0:
            job.track = "skip"  # not one of the target fields
            return job
        role_pts = 40 * min(best, 1.0)
        reasons.append(f"{best_name} role")

        # Skills (20)
        text = f"{job.title} {job.description}"
        matched = [s for s, rx in self.skills if rx and rx.search(text)]
        skill_pts = 20 * min(len(matched) / 5, 1.0)
        if matched:
            reasons.append("skills: " + ", ".join(matched[:5]))

        # Location (25)
        loc, why = self.location_score(job)
        if job.track == "part_time_now" and loc < 0.8:
            job.track = "skip"  # a part-time job has to be local or remote
            return job
        loc_pts = 25 * loc
        reasons.append(why)

        # Bonus (up to 10): veteran or clearance friendly
        bonus_pts = 0.0
        if self.bonus and self.bonus.search(job.description):
            bonus_pts += 5
            reasons.append("mentions veterans or clearance")
        if job.extra.get("veterans"):
            bonus_pts += 5
            reasons.append("veterans hiring path")

        # Freshness (5)
        fresh_pts = 0.0
        if job.posted:
            age = (self.now - job.posted).days
            if age <= 7:
                fresh_pts = 5
                reasons.append("posted this week")
            elif age <= 21:
                fresh_pts = 2.5

        job.score = round(min(role_pts + skill_pts + loc_pts + bonus_pts + fresh_pts, 100), 1)
        job.reasons = reasons
        return job
