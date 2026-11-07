"""Shared data types."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    source: str
    title: str
    company: str
    locations: list[str]
    url: str
    description: str = ""
    posted: datetime | None = None
    closes: datetime | None = None
    employment_type: str = ""  # e.g. "Part-time", "Full-time", "Intern"
    terms: list[str] = field(default_factory=list)  # e.g. ["Summer 2027"]
    remote: bool = False
    extra: dict = field(default_factory=dict)

    # Filled in by scoring
    track: str = ""  # "part_time_now", "summer_2027", "full_time", or "skip"
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    is_new: bool = False

    @property
    def key(self) -> str:
        """Stable id for de-duplication across sources and runs."""
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        company = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|company|global)\b", "", norm(self.company))
        raw = f"{norm(company)}|{norm(self.title)}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    @property
    def location_text(self) -> str:
        locs = "; ".join(self.locations) if self.locations else "Unknown"
        return f"{locs} (remote)" if self.remote and "remote" not in locs.lower() else locs
