# JobFinder · Israeli Jobs

A live index of open roles in Israeli hi-tech, public sector, academia, and healthcare.  
Built by [Jenny Sotnik Talisman](https://www.linkedin.com/in/jennysotnik/).

🔗 **[genys30.github.io/jobfinder](https://genys30.github.io/jobfinder/)**

---

## How it works

A GitHub Action runs every night at midnight (Israel time) and:

1. Scans [techmap](https://github.com/mluggy/techmap) to discover new companies
2. Merges with `companies.json` — the master registry of all tracked companies
3. Fetches open positions from each ATS (Comeet, Greenhouse, Lever, Ashby, Workable, Breezy)
4. Scrapes institutional sources (Mitam, Weizmann, BGU, HUJI, Technion)
5. Saves one CSV per source, updates `history.csv`
6. Deletes CSVs older than 7 days to keep the repo clean

LinkedIn data is added manually each morning by uploading a `linkedin_jobs_YYYY-MM-DD.csv` file.

The frontend (`index.html`) loads all CSVs directly in the browser — no backend, no database.

---

## Sources

| Category | Sources |
|---|---|
| Tech ATS | LinkedIn, Comeet, Greenhouse, Lever, Ashby, Workable, Breezy |
| Public & Defence | MOD, Mitam |
| Nonprofits & NGOs | Joint (JDC), Biltiformali |
| Academia | Weizmann, Technion, HUJI, TAU, BGU, Haifa, BAR |
| Healthcare | Clalit, Ichilov, Rambam, Hadassah, Soroka + 10 medical centers |
| Advisory | KPMG, Deloitte, EY, BIS, Osem-Nestlé |

---

## Company registry

All tracked companies live in `companies.json`.  
Each entry follows this schema:

```json
{
  "name": "Company Name",
  "greenhouse": null,
  "lever": null,
  "comeet": "slug/UID",
  "ashby": null,
  "workable": null,
  "breezy": null,
  "careers_url": "https://company.com/careers",
  "added_by": "manual",
  "added_date": "2026-05-30"
}
```

**To add a new company:**
1. Find the company's careers page
2. Identify which ATS they use and copy the token/slug
3. Add one entry to `companies.json`
4. Commit — it will be picked up by the next nightly run

**Fields:**
- `comeet` — format: `slug/UID` (e.g. `hibob/12.00A`)
- `greenhouse`, `lever`, `ashby`, `workable`, `breezy` — token only (e.g. `jfrog`)
- `careers_url` — fill in for manual entries so you remember the source
- `added_by` — `"manual"` or `"techmap"`
- `added_date` — fill in for manual entries (YYYY-MM-DD)

---

## Local setup

```bash
git clone https://github.com/Genys30/jobfinder.git
cd jobfinder

pip install requests beautifulsoup4

# Add your Mitam API key
export MITAM_API_KEY=your_key_here

python fetch_jobs.py
```

The script will generate `*_jobs_YYYY-MM-DD.csv` files and update `history.csv`.  
Open `index.html` in your browser to see the results.

---

## Repository structure

```
jobfinder/
├── index.html              # Frontend — filters, job list, analytics
├── fetch_jobs.py           # Nightly scraper — all ATS sources
├── companies.json          # Master company registry
├── history.csv             # Daily snapshot for analytics charts
├── fetch_jobs.yml          # GitHub Actions workflow
├── .gitignore
└── *_jobs_YYYY-MM-DD.csv   # Daily job exports (kept for 7 days)
```

---

## License

Data: [ODbL v1.0](https://opendatacommons.org/licenses/odbl/1-0/)  
Code: MIT
