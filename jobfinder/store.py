"""Remembers which jobs were already seen, so the report can flag new ones."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Job


def dedupe(jobs: list[Job]) -> list[Job]:
    """One entry per company + title; keep the one with the most detail."""
    best: dict[str, Job] = {}
    for job in jobs:
        cur = best.get(job.key)
        if cur is None:
            best[job.key] = job
            continue
        keep, other = (job, cur) if len(job.description) > len(cur.description) else (cur, job)
        for loc in other.locations:
            if loc not in keep.locations:
                keep.locations.append(loc)
        keep.terms = sorted(set(keep.terms) | set(other.terms))
        if other.source not in keep.source:
            keep.source = f"{keep.source}, {other.source}"
        best[job.key] = keep
    return list(best.values())


def mark_new(jobs: list[Job], path: Path, keep_days: int = 120) -> None:
    now = datetime.now(timezone.utc)
    seen: dict[str, str] = {}
    if path.exists():
        seen = json.loads(path.read_text())
    for job in jobs:
        if job.key not in seen:
            job.is_new = True
            seen[job.key] = now.isoformat(timespec="seconds")
    cutoff = now - timedelta(days=keep_days)
    seen = {k: v for k, v in seen.items() if datetime.fromisoformat(v) >= cutoff}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, indent=0, sort_keys=True))
