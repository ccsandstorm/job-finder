from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from jobfinder import report, store
from jobfinder.models import Job
from jobfinder.scoring import Scorer
from jobfinder.sources import adzuna, ats, simplify, usajobs

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def scorer():
    profile = yaml.safe_load((ROOT / "config/profile.yaml").read_text())
    return Scorer(profile, now=NOW)


def job(title, locations=("San Francisco, CA",), **kw):
    return Job(source="test", title=title, company=kw.pop("company", "Acme"), locations=list(locations),
               url="https://example.com", **kw)


# ---------- tracks ----------
@pytest.mark.parametrize(
    "title,terms,etype,expected",
    [
        ("Software Engineer Intern", ["Summer 2027"], "", "summer_2027"),
        ("Data Science Intern (Summer 2027)", [], "", "summer_2027"),
        ("Software Engineer Intern", [], "", "summer_2027"),
        ("Software Engineer Intern", ["Spring 2027"], "", "part_time_now"),
        ("Software Engineer Intern", ["Summer 2026"], "", "skip"),
        ("IT Help Desk Technician", [], "Part-time", "part_time_now"),
        ("Part-Time Data Analyst", [], "", "part_time_now"),
        ("Software Engineer", [], "Full-time", "full_time"),
    ],
)
def test_classify(scorer, title, terms, etype, expected):
    assert scorer.classify(job(title, terms=terms, employment_type=etype)) == expected


# ---------- scoring ----------
def test_target_role_in_sf_scores_high(scorer):
    j = scorer.score(job("Machine Learning Intern", terms=["Summer 2027"],
                         description="Python, SQL, PyTorch. Veterans encouraged.", posted=NOW - timedelta(days=2)))
    assert j.track == "summer_2027"
    assert j.score >= 80
    assert "in San Francisco" in j.reasons


def test_location_ranks_sf_over_far_away(scorer):
    sf = scorer.score(job("Software Engineer Intern"))
    ny = scorer.score(job("Software Engineer Intern", locations=["New York, NY"]))
    assert sf.score > ny.score


def test_remote_outside_us_is_not_remote(scorer):
    j = scorer.score(job("Software Engineer Intern", locations=["Remote in Canada"], remote=True))
    assert "remote outside the US" in j.reasons


def test_unrelated_and_senior_roles_are_skipped(scorer):
    assert scorer.score(job("Barista", employment_type="Part-time")).track == "skip"
    assert scorer.score(job("Senior Software Engineer")).track == "skip"
    assert scorer.score(job("Engineering Manager, Data")).track == "skip"


def test_part_time_must_be_local_or_remote(scorer):
    far = scorer.score(job("IT Support Technician", locations=["Denver, CO"], employment_type="Part-time"))
    near = scorer.score(job("IT Support Technician", locations=["Oakland, CA"], employment_type="Part-time"))
    assert far.track == "skip"
    assert near.track == "part_time_now"


def test_symbol_skills_match(scorer):
    j = scorer.score(job("Software Engineer Intern", description="Experience with C++ and C# required."))
    assert any("C++" in r and "C#" in r for r in j.reasons)


def test_veterans_hiring_path_bonus(scorer):
    base = scorer.score(job("IT Specialist Intern"))
    vet = scorer.score(job("IT Specialist Intern", extra={"veterans": True}))
    assert vet.score == base.score + 5


# ---------- parsers ----------
def test_simplify_parse_filters_inactive_and_grad_only():
    data = [
        {"active": True, "is_visible": True, "title": "SWE Intern", "company_name": "A", "locations": ["SF"],
         "url": "u", "terms": ["Summer 2027"], "degrees": ["Bachelor's"], "date_posted": 1794007540},
        {"active": False, "title": "Old", "company_name": "B", "locations": [], "url": "u"},
        {"active": True, "title": "PhD Intern", "company_name": "C", "locations": [], "url": "u", "degrees": ["PhD"]},
    ]
    jobs = simplify.parse(data)
    assert [j.title for j in jobs] == ["SWE Intern"]
    assert jobs[0].terms == ["Summer 2027"] and jobs[0].posted.year == 2026


def test_greenhouse_parse():
    data = {"jobs": [{"title": "Data Intern", "location": {"name": "Remote - US"},
                      "absolute_url": "u", "content": "&lt;p&gt;Use &amp;lt;b&amp;gt;Python&lt;/p&gt;",
                      "updated_at": "2026-11-01T10:00:00-07:00"}]}
    [j] = ats.parse_greenhouse(data, "Planet")
    assert j.company == "Planet" and j.remote and "Python" in j.description and "<" not in j.description


def test_lever_parse():
    data = [{"text": "IT Support (Part-time)", "hostedUrl": "u", "createdAt": 1793000000000,
             "categories": {"location": "San Francisco", "commitment": "Part-time"}, "descriptionPlain": "Help desk"}]
    [j] = ats.parse_lever(data, "Palantir")
    assert j.employment_type == "Part-time" and j.locations == ["San Francisco"]


def test_ashby_parse():
    data = {"jobs": [{"title": "SWE Intern", "location": "San Francisco", "employmentType": "Intern",
                      "jobUrl": "u", "isRemote": False, "isListed": True, "publishedAt": "2026-11-01T00:00:00Z",
                      "secondaryLocations": [{"location": "Remote"}]}]}
    [j] = ats.parse_ashby(data, "OpenAI")
    assert j.locations == ["San Francisco", "Remote"]


def test_usajobs_parse():
    data = {"SearchResult": {"SearchResultItems": [{"MatchedObjectDescriptor": {
        "PositionTitle": "Student Trainee (Information Technology)", "OrganizationName": "NASA",
        "PositionLocation": [{"LocationName": "Moffett Field, California"}], "PositionURI": "u",
        "PositionSchedule": [{"Name": "Part-time"}], "PublicationStartDate": "2026-11-01T00:00:00",
        "ApplicationCloseDate": "2026-11-20T23:59:59",
        "UserArea": {"Details": {"JobSummary": "<p>IT work</p>", "HiringPath": ["student", "vet"]}}}}]}}
    [j] = usajobs.parse(data)
    assert j.company == "NASA" and j.employment_type == "Intern" and j.extra["veterans"]
    assert j.closes.day == 20


def test_adzuna_parse():
    data = {"results": [{"title": "<strong>Help Desk</strong> Technician", "company": {"display_name": "X"},
                         "location": {"display_name": "Oakland, CA"}, "redirect_url": "u",
                         "description": "desc", "created": "2026-11-05T00:00:00Z", "contract_time": "part_time"}]}
    [j] = adzuna.parse(data)
    assert j.title == "Help Desk Technician" and j.employment_type == "Part-time"


def test_sources_without_keys_are_skipped(monkeypatch):
    for var in ("USAJOBS_API_KEY", "USAJOBS_EMAIL", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert usajobs.fetch({"queries": [{}]}) == []
    assert adzuna.fetch({"queries": [{}]}) == []


# ---------- store and report ----------
def test_dedupe_merges_company_variants():
    a = job("Software Engineering Intern", company="KLA", description="short")
    b = job("Software Engineering Intern", company="KLA Corporation", locations=["Milpitas, CA"],
            description="a much longer description")
    [merged] = store.dedupe([a, b])
    assert merged.description == "a much longer description"
    assert set(merged.locations) == {"San Francisco, CA", "Milpitas, CA"}


def test_mark_new_only_flags_unseen(tmp_path):
    path = tmp_path / "seen.json"
    first = [job("A Intern")]
    store.mark_new(first, path)
    again = [job("A Intern"), job("B Intern")]
    store.mark_new(again, path)
    assert first[0].is_new and not again[0].is_new and again[1].is_new


def test_reports_written(tmp_path, scorer):
    jobs = [scorer.score(job("Data Science Intern", terms=["Summer 2027"])),
            scorer.score(job("Help Desk <Tech>", employment_type="Part-time"))]
    report.write_all(jobs, tmp_path)
    page = (tmp_path / "index.html").read_text()
    assert "Data Science Intern" in page and "Help Desk &lt;Tech&gt;" in page
    assert (tmp_path / "jobs.csv").read_text().count("\n") == 3
    assert "Summer 2027 internships (1)" in (tmp_path / "README.md").read_text()
