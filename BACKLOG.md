# JobFinder · Backlog

Items discovered during the May 2026 refactor session that were intentionally deferred.

---

## 🔴 High Priority

### ~~Missing scrapers — KPMG shows "no file yet"~~ ✅ Resolved 2026-06-04
KPMG routes through Comeet as *Somekh Chaikin* (`"comeet": "somekhchaikin/F3.007"` in
`companies.json`). The entry was already correct, but Comeet API returns 403 from
GitHub Actions (datacenter IP not in allowlist). Fix: added `fetch_jobs.py` as step 22
in `run_fetch.bat` so it runs locally each morning with an Israeli IP. KPMG now populates
via the regular `comeet_jobs_*` CSV.

**Done so far:** TAU ✅, Haifa ✅, BAR ✅, Shaare Zedek ✅, Hadassah ✅, Ichilov ✅, GotFriends ✅, HUJI positions ✅, BIS ✅, Joint ✅, Deloitte ✅, EY ✅, Osem ✅, KPMG ✅

### ~~Lever — 5 companies returning 404~~ ✅ Resolved 2026-05-30
- Contrast Security Israel → no open positions → `active: false`
- CYE → no open positions → `active: false`
- Digital Turbine → moved to Workday (not supported) → `active: false`
- Sauce → Lever 403 blocked → `active: false`
- Vault Platform → no open positions → `active: false`

### ~~HUJI Alumni Career — wrong output filename~~ ✅ Resolved 2026-06-02
### ~~Clalit scraper not running~~ ✅ Resolved 2026-06-02
### ~~TAU scraper~~ ✅ Resolved 2026-06-02
### ~~Haifa University scraper~~ ✅ Resolved 2026-06-02
### ~~Bar-Ilan (BAR) scraper~~ ✅ Resolved 2026-06-03
### ~~Clalit medical centers showing 0 jobs~~ ✅ Resolved 2026-06-03
### ~~Shaare Zedek + Hadassah hospitals~~ ✅ Resolved 2026-06-03
### ~~Ichilov · GotFriends · HUJI positions~~ ✅ Resolved 2026-06-03
### ~~BIS · Joint · Deloitte · EY~~ ✅ Resolved 2026-06-03
### ~~Osem-Nestlé — convert from source to company (option B)~~ ✅ Resolved 2026-06-03

### ~~`first_seen` date preservation for no-date sources~~ ✅ Resolved 2026-06-06/07
### ~~Data bar not reflecting active filters (Maccabi/Leumit/Meuhedet/hospitals)~~ ✅ Resolved 2026-06-07
### ~~Multi-select filters~~ ✅ Resolved 2026-06-07

Sources that don't publish a `date_posted` were writing `TODAY` on every run, causing
all their jobs to appear in the "Today" filter daily. Fixed by adding a `load_first_seen()`
helper to each affected scraper: on each run it reads the previous day's CSV and preserves
the original discovery date for existing jobs; only truly new jobs get today's date.

**Patched in `fetch_jobs.py`** (key: URL unless noted):
- `run_weizmann`, `run_technion`, `run_leumit`, `run_movement`, `run_innovation_israel`
- `run_bgu` — key: title (all BGU jobs share one listing URL)

**Patched in `fetch_maccabi.py`** — key: URL

**Not patched** (already have real publication dates):
- Clalit, Meuhedet (`JobTimeSortAttr`), Ichilov (`activationDate`), BAR (`activationDate`)

Six filters converted to multi-select (checkbox panels): Role, Level, Employer Type,
Source, Type (worktype), Contract. See ARCHITECTURE.md §4a for details.

---

## 📦 Google Drive archive (set up 2026-06-02)

CSV history is now archived to Google Drive instead of bloating the repo. The repo keeps
only the last 7 days of `*_jobs_*` files; the full history lives on Drive.

- **Account:** sncentral.data@gmail.com
- **Folder:** `jobfinder-data` (ID `18_hQPxPgpkbHwFoevdDgSq2yCAeEw5LU`)
- **Nightly upload:** GitHub Actions installs rclone and uploads via `RCLONE_TOKEN` secret
- **Manual upload:** `run_fetch.bat` step [23/23] uploads all CSVs via local rclone config
- **Upload pattern:** `*.csv` (covers `*_jobs_*`, `jobs_telegram_*`, `huji_positions_*`, etc.)
- rclone only transfers new/changed files, so daily runs are cheap

**Orphan scrapers (do NOT wire into runners — duplicates):**
- `fetch_huji.py`, `fetch_bgu_extra.py`, `fetch_jobs_from_companies.py`, `fetch_mitam.py`, `fetch_weizmann.py`

---

## 📊 Google Sheets Analytics Dashboard (built 2026-06-04)

Full analytics pipeline reading job CSVs from Google Drive via Google Apps Script.

- **Spreadsheet:** Jobfinder-Analytics (account: sotnik@gmail.com, Drive folder shared from sncentral.data@gmail.com)
- **Script:** `Code.gs` (Apps Script, ~1200 lines)
- **Daily trigger:** 07:00 via `setupTrigger()` — runs `importIncremental`
- **Manual update:** Extensions → Apps Script → Run `importIncremental`

**Sheets:**

| Sheet | Contents |
|---|---|
| Raw | 36,062 unique jobs deduped by URL (full history from April 2026) |
| Daily | Jobs per source per day — 374 days × 35 sources |
| Companies | 4,137 companies with total, last_30d, prev_30d, first_seen, hiring_status |
| Roles | All departments ranked + workplace type breakdown |
| Market | Dept × Month pivot (34 depts × 40 months) with MoM % |
| Dashboard | KPI summary + 4 live QUERY formula tables |
| Charts | 5 charts: dept trend, Apr vs May, top companies, workplace pie, sources |
| Weekly | Last 7 days snapshot: KPIs, by dept/source/company, top 50 jobs table |

**Key functions in Code.gs:**

- `resetAndImport()` — full reload from scratch (clears Raw, re-imports all 1017 files)
- `continueImport()` — continue interrupted import from checkpoint
- `importIncremental()` — daily update, new files only
- `reclassifyRaw()` — reclassify all dept/company fields in Raw (run after classifyTitle changes)
- `continueReclassify()` — continue interrupted reclassification
- `buildCharts()` — rebuild Charts sheet manually
- `buildWeekly()` — rebuild Weekly sheet manually
- `debugOther()` — show top titles in "Other" category (for improving classifyTitle)
- `setupTrigger()` — set daily 07:00 trigger (one-time)

**Title classification (`classifyTitle`):**
Function maps job titles to 20 standard categories using keyword matching + `DEPT_MAP` lookup.
Categories: R&D & Engineering, Data & AI, DevOps & Cloud, Cyber & Security, Embedded & Hardware,
QA & Automation, Product, Solutions Engineering, Sales, Marketing, HR & Recruiting,
Finance & Accounting, Legal & Compliance, Operations & Logistics, Management & Executive,
Support & Customer Success, Design, Medical & Clinical, Academic & Research,
Defense & Aerospace, FinTech, IT, Technology Consulting, Other.

**Stats after reclassification (2026-06-04):**
- Other reduced from 10,153 → 5,468 (46% improvement)
- Departments: 473 → 34 clean categories
- Companies: 4,978 → 4,137 (LinkedIn artifacts cleaned)
- Workplace types: 12 → 7 (normalised onsite/on-site, fulltime/full_time etc.)

**Known issues / next steps:**
- `Other` still contains ~5,468 rows — mostly agency names in title field (GotFriends,
  Club Med resort jobs, Telugu micro-tasks, company names like "nvidia", "comblack")
- `workplace_type` normalisation needs to be applied in scrapers too (not just in Sheets)

---

## 🛠 `run_fetch.bat` step reference (as of 2026-06-04)

The manual local runner now has 23 steps:
1. git pull --rebase (with `git reset --hard` + LinkedIn CSV backup/restore)
2. Telegram @biltiformali · 3. Rambam · 4. BGU · 5. Maccabi · 6. MOD
7. Clalit · 8. TAU · 9. Haifa · 10. Bar-Ilan
11. Ichilov · 12. GotFriends · 13. HUJI positions
14. Shaare Zedek (PW) · 15. Hadassah (PW)
16. Deloitte (PW) · 17. EY (PW) · 18. BIS (PW) · 19. Joint (PW)
20. Osem-Nestlé (curl_cffi) · 21. Teva (req)
22. `fetch_jobs.py` — ATS sources (Comeet incl. KPMG, Greenhouse, Lever, Ashby)
23. rclone upload all CSVs → Google Drive
+ commit + push

---

## 🟡 Medium Priority

### LinkedIn — manual upload every morning
Currently scraped manually each morning and uploaded as `linkedin_jobs_YYYY-MM-DD.csv`.

**Action:** Investigate automation options. LinkedIn blocks most scrapers, but tools like Apify or a browser extension could help.

### Workable / Breezy — frozen sources, revisit in ~1 month
Both sources were frozen (`active: false`) because their APIs return 403 from GitHub Actions.

**Action:** Check in ~1 month whether the APIs have opened up.

Companies frozen:
- **Workable:** Atera Networks, BigPanda, Cloudinary, Healthy.io, Innovid, Papaya Global, Poptin, SolarEdge Technologies, Trustmi, Vayyar Imaging
- **Breezy:** Ayyeka, Dalet, Descope Technologies, Insights.US, Lynx.MD

### Role filter expansion in jobfinder (frontend)
The current Role filter has 13 options. Should be expanded to match the 20 categories
used in the analytics dashboard:

R&D & Engineering, Data & AI, DevOps & Cloud, Cyber & Security, Embedded & Hardware,
QA & Automation, Product, Solutions Engineering, Sales, Marketing, HR & Recruiting,
Finance & Accounting, Legal & Compliance, Operations & Logistics, Management & Executive,
Support & Customer Success, Design, Medical & Clinical, Academic & Research,
Defense & Aerospace, FinTech, IT, Technology Consulting.

Note: adding new options to multi-select filters is now simple — just add `<li class="ms-item" data-value="...">` rows to the panel in `index.html`.

### `workplace_type` normalisation in scrapers
Currently normalised only in Apps Script (`normaliseWorkplace()`). Should also be
normalised at scrape time in `fetch_jobs.py` and other scrapers so the site frontend
also benefits. Standard values: `remote`, `hybrid`, `onsite`, `full_time`, `part_time`.

---

## 🟢 Low Priority

### Ashby — only 2 companies tracked
**Action:** Find more Israeli companies using Ashby ATS and add them to `companies.json`.

### BGU — intermittently returns 0 jobs
**Action:** Monitor over time. No fix needed unless it stays at 0 for weeks.

### Node.js 20 deprecation warning in GitHub Actions
**Action:** Update `.github/workflows/fetch_jobs.yml`:
- `actions/checkout@v4` → `actions/checkout@v4.2.2`
- `actions/setup-python@v5` → `actions/setup-python@v5.6.0`

---

## 💡 Ideas (no timeline)

- **Email alerts** — notify when a source fails for 3+ consecutive days
- **Company health check** — weekly script that pings each ATS token and flags dead ones
- **Salary data** — enrich jobs with salary ranges where available
- **Duplicate detection** — same job appearing via LinkedIn and Comeet
- **Comeet description scraping** — `fetch_jobs.py` doesn't scrape full descriptions for Comeet, causing Comeet jobs to always appear in "No Description"

---

*Last updated: 2026-06-07*
