# JobFinder · Backlog

Items discovered during the May 2026 refactor session that were intentionally deferred.

---

## 🔴 High Priority

### Israeli engineering-colleges expansion (template-first)
Adding each engineering college's **own** open positions (employer-type `academic`), mirroring
the university sources. Afeka is the proven end-to-end template; the rest replicate its pattern.

- **Afeka** ✅ Resolved 2026-06-21 — `fetch_afeka.py` → `afeka_jobs_*.csv` (11 jobs: 9 admin +
  2 academic faculty). req+BS4 on the Umbraco "Working at Afeka" page (Bootstrap accordion
  `div.accordion-item`); local-only (step 11/26 in `run_fetch.bat`). `first_seen` by **title**
  (shared page URL, BGU pattern), job-marker filter drops the events accordion,
  `detect_department` classifies admin/academic **by title only**. Frontend dedup by `title+url`
  (academic jobs share the page URL). Full wiring in `index.html`. See ARCHITECTURE §3/§8/§11.
- **SCE (Sami Shamoon)** ✅ Resolved 2026-06-21 — `fetch_sce.py` → `sce_jobs_*.csv` (20 jobs:
  9 admin + 8 academic + 3 research). **Playwright** (WAF JS-challenge — requests & curl_cffi
  both 403; one shared context warms up on the hub, then visits 3 sub-pages); local-only
  (step 12/27). **Mixed links**: admin → external CIVI ATS (keep `&src=` or it 404s),
  academic/research → internal SCE detail pages; selector matches CIVI promo OR child-of-subpage.
  Real per-job URLs → `first_seen`/dedup by **url**. v1 no descriptions. See ARCHITECTURE §3/§8/§11.
- **Braude (ORT)** ✅ Resolved 2026-06-21 — `fetch_braude.py` → `braude_jobs_*.csv` (17 jobs:
  9 admin + 8 academic), Karmiel. WordPress, **no WAF** → req+BS4 (easiest college; Afeka
  template, worked first try). Foundation accordion `li.accordion-item`; **descriptions inline**
  (pop-up works, unlike SCE); two sections → `department` by nearest preceding heading. No
  per-job URL (apply by email) → `first_seen` by **title**, dedup `title+url`. Local-only
  (step 13/27). See ARCHITECTURE §3/§8/§11.
- **HIT (Holon)** ✅ Resolved 2026-06-22 — `fetch_hit.py` → `hit_jobs_*.csv` (15 jobs:
  2 admin + 13 academic). **curl_cffi** `chrome110` (Sucuri/SPD gateway 302-loops plain
  requests → //abuse.spd.co.il; warm-up on home + retries, like Osem); local-only (step 14/28).
  Two-tab Bootstrap accordion (`#JOB_accordion0` admin / `#JOB_accordion1` academic),
  descriptions inline (pop-up works). **Duplicate-title gotcha**: two postdocs share the title
  "משרת פוסטדוק | Postdoctoral Position" → unique `#collapseN` id appended to page URL as
  fragment to keep them separate (dedup/first_seen by **url**). internship regex tightened to
  word boundaries (was matching "INTERNational"). See ARCHITECTURE §3/§8/§11.
- **Azrieli College** ✅ Resolved 2026-06-22 — `fetch_azrieli.py` → `azrieli_jobs_*.csv` (10 jobs:
  5 academic + 5 admin), Jerusalem. **curl_cffi** `chrome110` (plain requests 403; warm-up +
  retries, like HIT/Osem); local-only (step 15/29). WordPress `roots-mipo` custom accordion,
  two sections (`#academic-staff` / `#administrative-staff` → `department` by id), descriptions
  inline (pop-up works). No per-job URL → `first_seen` by **title**, dedup `title+url`. Worked
  first try. See ARCHITECTURE §3/§8/§11.

- **Shenkar** ✅ Resolved 2026-06-23 — `fetch_shenkar.py` → `shenkar_jobs_*.csv` (6 jobs, all
  academic faculty), Ramat Gan; the 6th engineering/tech college. WordPress, **no WAF** →
  req+BS4. **Different structure**: flat list of links to **external Google Docs/Drive** docs
  (no inline descriptions — `description` empty, pop-up blank); links are real per-job URLs →
  dedup/`first_seen` by **url** (SCE pattern). All faculty → `department=academic_faculty`.
  Local-only (step 16/30). See ARCHITECTURE §3/§8/§11.

**✅ Engineering/tech-colleges branch COMPLETE (6/6):** Afeka (req) · SCE (PW) · Braude (req) ·
HIT (cffi) · Azrieli (cffi) · Shenkar (req). All six engineering/technology colleges done.

**General-colleges branch (scope = academic + admin) — 2/4 done:**
- **Sapir** ✅ Resolved 2026-06-24 — `fetch_sapir.py` → `sapir_jobs_*.csv` (~21 jobs, mostly
  admin), Sderot. CIVI ATS feed (`app.civi.co.il/promos/id=NLY65YEJTW&src=13586`), scraped
  directly; dedup by per-job promo **url**. **Pagination via `&p=N`** (`?rows=` ignored).
  Frontend uses `--spr` colour (`--sp` was taken by Direct). Step 17/32. See ARCHITECTURE §3/§8/§11.
- **Emek Yezreel** ✅ Resolved 2026-06-24 — `fetch_yvc.py` → `yvc_jobs_*.csv` (~5 jobs, academic
  course positions), Yezreel Valley. req+BS4 (no WAF), `section.q-and-a` accordion. **Source key
  `yvc`** (not `emek` — `EMEK_JOBS` = HaEmek hospital). Duplicate toggle titles enriched with the
  course name (HIT-style); dedup by enriched title. Step 18/32. See ARCHITECTURE §3/§8/§11.
- **Tel-Hai** ⏳ queued — `telhai.ac.il/jobs` + `/jobs-2` (req, no WAF; academic page may be a
  generic "send CV" page rather than a list — check on recon).
- **Ruppin** ⏳ LAST, separate go/no-go — `ruppin.ac.il/.../academic-staff-required` is behind
  **Imperva (status 247)**: req AND curl_cffi both blocked → needs Playwright. Low relevance
  (mostly maintenance/secretary/marketing). Weigh PW cost vs. yield before committing.

Per-college flow: audit career page → spec → confirm → `fetch_{college}.py` → verify rows →
frontend wiring → `run_fetch.bat` step → prod check. Check for shared platforms first
(HunterHRMS like HUJI/Shaare Zedek, RedMatch/TopMatch like BAR/Ichilov) — those need only a new
GUID/subdomain, not a fresh parser.

### ~~Analytics `Raw` frozen — import checkpoint ordered by filename~~ ✅ Resolved 2026-06-15
`processBatch` compared Drive files by full name (`f.name > checkpoint`). Filenames begin with
the source, so `workable_jobs_…` (last alphabetically) became the checkpoint each day and every
file named before "workable" on later dates was skipped — `Raw` silently froze at 2026-06-04
while Drive had files through the 15th (Weekly showed Week1=0, Dashboard last30 under-counted).
Fix: order/compare by `fileKey(name)` = `"YYYY-MM-DD|filename"` (date first). `processBatch`
self-heals a legacy checkpoint; `migrateCheckpointFormat()` does it manually. `Raw` rebuilt with
`hardResetRaw()` + repeated `continueImport()` (46,778 rows). See ARCHITECTURE §10/§11.

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

## 🛠 `run_fetch.bat` step reference (as of 2026-06-22)

The manual local runner now has 32 steps:
1. git pull --rebase (with `git reset --hard` + LinkedIn CSV backup/restore + auto URL-clean via `clean_linkedin_csv.py`)
2. Telegram @biltiformali · 3. Rambam · 4. BGU · 5. Maccabi · 6. MOD
7. Clalit · 8. TAU · 9. Haifa · 10. Bar-Ilan · **11. Afeka** · **12. SCE (PW)** · **13. Braude** · **14. HIT (cffi)** · **15. Azrieli (cffi)** · **16. Shenkar** · **17. Sapir (CIVI)** · **18. Emek Yezreel (YVC)**
19. Ichilov · 20. GotFriends · 21. HUJI positions
22. Shaare Zedek (PW) · 23. Hadassah (PW)
24. Deloitte (PW) · 25. EY (PW) · 26. BIS (PW) · 27. Joint (PW)
28. Osem-Nestlé (curl_cffi) · 29. Teva (req)
30. health check (`check_health.py`)
31. rclone upload all CSVs → Google Drive
32. commit + push
27. commit + push

Note: `fetch_jobs.py` (ATS sources) and `fetch_gotfriends.py` run in **GitHub Actions CI**, not
in the bat.

---

## 🟡 Medium Priority

### ~~LinkedIn — file size bloat~~ ✅ Resolved 2026-06-12
LinkedIn CSV URLs contained tracking parameters (`?eBP=...&refId=...&trackingId=...`)
making each file ~487 KB (84% of size = URL noise). Added `clean_linkedin_csv.py` which
strips params and keeps only the canonical `/jobs/view/ID/` URL (46 chars vs 519 avg).
`run_fetch.bat` now runs the script automatically after LinkedIn restore — no manual step.
File size: 487 KB → 118 KB. Also added outer try/catch to `loadLinkedIn()` so status
shows `"failed to load"` instead of frozen `"loading…"` on any error.

### ~~LinkedIn — "no files found" while recent files exist~~ ✅ Resolved 2026-06-14
`loadLinkedIn()` showed "no files found — upload …" even though `linkedin_jobs_*` files
from the last several days were present in the repo. Cause: the file-discovery loop was
`for(let i=0;i<2;i++)` — it only probed **today + yesterday**, despite the comment and
`ARCHITECTURE.md` claiming a 7-day window. With today's and yesterday's files missing
(today not yet uploaded, yesterday absent), the newest existing file (`06-12`, 2 days back)
fell outside the window → empty result. Fix: changed the window to `for(let i=0;i<7;i++)`
in `loadLinkedIn()` only. Dedup (by `title+company+city`) already collapses the duplicate
listings across the extra days. Other loaders left at `i<2` — CI sources always have a
fresh same-day file, so they're unaffected.

### LinkedIn — manual upload every morning
Currently scraped manually each morning and uploaded as `linkedin_jobs_YYYY-MM-DD.csv`.

**Action:** Investigate automation options. LinkedIn blocks most scrapers, but tools like Apify or a browser extension could help.

### LinkedIn — `date` column is the scrape date, not the real publish date (known limitation)
The `date` column in `linkedin_jobs_*.csv` is stamped with the **scrape/run date**, not the
employer's actual publication date — every row in a given day's file carries that day's date
(e.g. all rows in `linkedin_jobs_2026-06-12.csv` = `06/12/2026`). `normLinkedIn` maps this
column to `job.updated`, and the "Posted" filter (`Today` / `3 days` / `7 days`) filters on
`job.updated`.

**Consequence:** for LinkedIn, "Posted = 3 days" means *seen in a scrape within the last 3
days*, not *published within the last 3 days*. A job that has been live on LinkedIn for weeks
still appears under "3 days" if it was scraped recently. Sources with a real API publish date
(Comeet, Ichilov, Meuhedet, BAR, etc.) are unaffected — they filter by true publication date.
On dedup (sort by date desc, keep newest), a recurring job keeps the most recent scrape date,
so long-standing listings refresh their date to the latest file they appear in. The "Today"
filter is **not** polluted by loading older files: older rows carry older dates and fall below
the midnight cutoff.

**Action (deferred, needs discussion):** Apply `first_seen`-style logic to LinkedIn — extend
`clean_linkedin_csv.py` to read the previous day's CSV and preserve the original discovery date
for recurring jobs, stamping today's date only on genuinely new rows. Mirrors the `first_seen`
helper already used in the other no-date scrapers (see "first_seen date preservation", resolved
2026-06-06/07).

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

### TitleTrends — residual title-normalization noise (low)
`analyzeTitleTrends` groups by normalized title correctly, but the displayed `title`/sample can
still show artifacts: numeric IDs (`POST0709`, `22771 - SAP MM Software Tester`,
`Splunk Developer (1006777)`) and company-name-in-title swap rows (`IAI - Israel Aerospace
Industries`) that `isGarbageRow_` misses when the company field is empty.

**Action:** strip standalone ID tokens/prefixes in `normalizeTitleForTrends_` display path and
flag "company-looking" titles when company is blank. Cosmetic only — grouping is unaffected.

**Note (2026-06-16):** `buildLinkedInPost`'s `cleanTitleForPost_` already does this cosmetically
for the LinkedIn draft (strips `- 236606`, `(copy)`, emoji/ID tails). The core fix in
`normalizeTitleForTrends_` — so grouping itself collapses these variants — is still open.

## 💡 Ideas (no timeline)

- **Auto-draft LinkedIn post on schedule** — chain `buildLinkedInPost()` onto the Sunday 08:00
  `analyzeTitleTrends` trigger so the weekly `LinkedInPost` draft is ready without a manual run.

- **Email alerts** — notify when a source fails for 3+ consecutive days
- **Company health check** — weekly script that pings each ATS token and flags dead ones
- **Salary data** — enrich jobs with salary ranges where available
- **Duplicate detection** — same job appearing via LinkedIn and Comeet
- **Comeet description scraping** — `fetch_jobs.py` doesn't scrape full descriptions for Comeet, causing Comeet jobs to always appear in "No Description"

---

*Last updated: 2026-06-22*
