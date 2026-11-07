# job-finder

Finds tech jobs and internships every day and ranks them against my resume and goals:

1. **Part-time and school-year roles now**: part-time tech jobs and fall, winter, or spring internships in the Bay Area or remote.
2. **Summer 2027 internships**: the internship before senior year at USF.
3. **Entry-level full-time roles**: for tracking which companies hire in my fields.

**[Today's report](reports/README.md)** · [full table (CSV)](reports/jobs.csv)

## How it works

```
sources ──► de-duplicate ──► sort into tracks ──► score 0–100 ──► reports/
```

**Sources.** Everything here comes from APIs or data that allow automated access. LinkedIn, Indeed, Glassdoor, and Handshake prohibit scraping, so they aren't used directly. The sources below cover most of the same postings.

| Source | What it covers | Key needed |
|---|---|---|
| [SimplifyJobs lists](https://github.com/SimplifyJobs/Summer2027-Internships) | ~5,000 open tech internships and new-grad roles, updated daily | No |
| Greenhouse, Lever, Ashby | Careers pages of chosen companies (`config/sources.yaml`) | No |
| [USAJOBS](https://developer.usajobs.gov/) | Federal jobs, including Pathways student internships and veteran hiring paths | Free |
| [Adzuna](https://developer.adzuna.com/) | Job-board aggregator; good for local part-time jobs | Free |

**Scoring** (`jobfinder/scoring.py`, tuned in `config/profile.yaml`):

| Part | Points | Based on |
|---|---|---|
| Role fit | 40 | Title or description matches software, data, AI/ML, satellite/RF, or IT support |
| Skills | 20 | Python, Java, SQL, C++, networking, and other skills from my resume |
| Location | 25 | San Francisco > Bay Area > US remote > rest of California > elsewhere |
| Bonus | 10 | Mentions veterans or clearance, or a USAJOBS veterans hiring path |
| Freshness | 5 | Posted in the last week |

Senior, manager, PhD-only, and unrelated roles are dropped. Part-time roles must be local or remote.

## Run it

```bash
pip install -r requirements.txt
python -m jobfinder                      # all sources
python -m jobfinder --sources simplify   # only the internship lists
python -m pytest                         # tests
```

Open `reports/index.html` in a browser for a filterable table.

## Daily run

`.github/workflows/daily.yml` runs every morning on GitHub Actions and commits the new report. To run it now: **Actions → Daily job search → Run workflow**.

To turn on USAJOBS and Adzuna, add these under **Settings → Secrets and variables → Actions**:

- `USAJOBS_API_KEY`, `USAJOBS_EMAIL` (request a key at developer.usajobs.gov)
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (sign up at developer.adzuna.com)

## Customize

- `config/profile.yaml`: target roles, skills, locations, and titles to skip.
- `config/sources.yaml`: companies to watch and search queries.
