"""Run every source, score the results, and write the reports.

    python -m jobfinder                       # all sources
    python -m jobfinder --sources simplify    # just the internship lists
"""
from __future__ import annotations

import argparse
import logging
from collections import Counter
from pathlib import Path

import yaml

from . import report, store
from .scoring import Scorer
from .sources import adzuna, ats, simplify, usajobs

SOURCES = {"simplify": simplify, "ats": ats, "usajobs": usajobs, "adzuna": adzuna}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jobfinder")
    ap.add_argument("--config", type=Path, default=Path("config"))
    ap.add_argument("--out", type=Path, default=Path("reports"))
    ap.add_argument("--seen", type=Path, default=Path("data/seen.json"))
    ap.add_argument("--sources", default=",".join(SOURCES), help="comma-separated: " + ",".join(SOURCES))
    ap.add_argument("--limit", type=int, default=100, help="max jobs per list in the report")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("jobfinder")

    profile = load_yaml(args.config / "profile.yaml")
    sources_cfg = load_yaml(args.config / "sources.yaml")

    jobs = []
    for name in [s.strip() for s in args.sources.split(",") if s.strip()]:
        mod = SOURCES[name]
        found = mod.fetch(sources_cfg.get(name) or {})
        log.info("%s: %d jobs", name, len(found))
        jobs += found

    jobs = store.dedupe(jobs)
    scorer = Scorer(profile)
    for job in jobs:
        scorer.score(job)
    kept = [j for j in jobs if j.track != "skip"]
    store.mark_new(kept, args.seen)
    report.write_all(kept, args.out, args.limit)

    counts = Counter(j.track for j in kept)
    log.info("kept %d of %d jobs: %s", len(kept), len(jobs), dict(counts))
    log.info("report written to %s", args.out / "index.html")
    return 0
