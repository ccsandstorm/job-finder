"""Writes the ranked lists as an HTML page, a Markdown summary, and a CSV."""
from __future__ import annotations

import csv
import html
from datetime import datetime, timezone
from pathlib import Path

from .models import Job

TRACKS = [
    ("part_time_now", "Part-time and school-year roles (now)",
     "Part-time jobs and fall, winter, or spring internships you can do around classes."),
    ("summer_2027", "Summer 2027 internships",
     "The internship before your senior year. Most big companies close applications by winter, so apply early."),
    ("full_time", "Entry-level full-time roles",
     "Not the goal yet, but useful for seeing which companies hire in your fields."),
]


def _date(dt: datetime | None) -> str:
    return dt.strftime("%b %d") if dt else ""


def ranked(jobs: list[Job], track: str, limit: int) -> list[Job]:
    picks = [j for j in jobs if j.track == track]
    picks.sort(key=lambda j: (j.score, j.posted or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return picks[:limit]


def write_csv(jobs: list[Job], path: Path, limit: int = 300) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["track", "score", "new", "title", "company", "location", "type", "terms",
                    "posted", "closes", "source", "url", "why"])
        for j in (j for track, _, _ in TRACKS for j in ranked(jobs, track, limit)):
            w.writerow([j.track, j.score, "yes" if j.is_new else "", j.title, j.company, j.location_text,
                        j.employment_type, "; ".join(j.terms), _date(j.posted), _date(j.closes),
                        j.source, j.url, "; ".join(j.reasons)])


def write_markdown(jobs: list[Job], path: Path, limit: int, generated: datetime) -> None:
    lines = [f"# Job finder report", "", f"_Updated {generated:%B %d, %Y}_", ""]
    for track, title, blurb in TRACKS:
        picks = ranked(jobs, track, limit)
        lines += [f"## {title} ({len(picks)})", "", blurb, "",
                  "| Score | Role | Company | Location | Posted |", "|---|---|---|---|---|"]
        for j in picks:
            new = " 🆕" if j.is_new else ""
            role = j.title.replace("|", "/")
            lines.append(f"| {j.score:.0f} | [{role}]({j.url}){new} | {j.company.replace('|', '/')} | "
                         f"{j.location_text.replace('|', '/')} | {_date(j.posted)} |")
        lines.append("")
    path.write_text("\n".join(lines))


def write_html(jobs: list[Job], path: Path, limit: int, generated: datetime) -> None:
    e = html.escape
    sections = []
    for track, title, blurb in TRACKS:
        picks = ranked(jobs, track, limit)
        rows = []
        for j in picks:
            new = '<span class="new">NEW</span> ' if j.is_new else ""
            closes = f'<div class="muted">Closes {_date(j.closes)}</div>' if j.closes else ""
            rows.append(
                f'<tr><td class="score">{j.score:.0f}</td>'
                f'<td>{new}<a href="{e(j.url)}" target="_blank" rel="noopener">{e(j.title)}</a>'
                f'<div class="muted">{e(", ".join(j.reasons))}</div></td>'
                f"<td>{e(j.company)}</td><td>{e(j.location_text)}</td>"
                f"<td>{_date(j.posted)}{closes}</td><td class=\"muted\">{e(j.source)}</td></tr>"
            )
        body = "".join(rows) or '<tr><td colspan="6" class="muted">Nothing matched today.</td></tr>'
        sections.append(
            f'<section><h2>{e(title)} <span class="count">{len(picks)}</span></h2>'
            f'<p class="muted">{e(blurb)}</p><div class="wrap"><table>'
            f"<thead><tr><th>Score</th><th>Role</th><th>Company</th><th>Location</th><th>Posted</th>"
            f"<th>Source</th></tr></thead><tbody>{body}</tbody></table></div></section>"
        )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Finder</title>
<style>
:root{{--bg:#fff;--fg:#1d2733;--muted:#5f6b7a;--line:#e3e7ec;--accent:#1f3a5f;--new:#0a7d4f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12161c;--fg:#e6ebf1;--muted:#98a4b3;--line:#2a313b;--accent:#8fb4e3;--new:#4fd19a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{margin:0 0 4px;color:var(--accent)}} h2{{margin:32px 0 4px;color:var(--accent)}}
.count{{font-size:.7em;color:var(--muted)}} .muted{{color:var(--muted);font-size:.85em}}
input{{width:100%;box-sizing:border-box;padding:10px;margin:16px 0 0;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg);font:inherit}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;min-width:640px}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:.8em;text-transform:uppercase;color:var(--muted)}} td.score{{font-weight:700;font-variant-numeric:tabular-nums}}
a{{color:var(--accent)}} .new{{color:var(--new);font-weight:700;font-size:.75em}}
</style></head><body><main>
<h1>Job Finder</h1><div class="muted">Updated {generated:%B %d, %Y at %H:%M} UTC. Ranked against Carl's resume and goals.</div>
<input id="q" placeholder="Filter by company, role, or location" oninput="f(this.value)">
{''.join(sections)}
</main><script>
function f(q){{q=q.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>{{r.style.display=r.textContent.toLowerCase().includes(q)?'':'none'}})}}
</script></body></html>"""
    path.write_text(page)


def write_all(jobs: list[Job], out_dir: Path, limit: int = 100) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    write_html(jobs, out_dir / "index.html", limit, now)
    write_markdown(jobs, out_dir / "README.md", limit, now)
    write_csv(jobs, out_dir / "jobs.csv")
