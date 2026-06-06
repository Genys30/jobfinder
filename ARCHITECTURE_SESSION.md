### 2026-06-04 (session 2)
- **Google Sheets Analytics Dashboard** built from scratch:
  - `Code.gs` (~1200 lines) reads all job CSVs from Google Drive via Apps Script
  - Incremental load with filename-based checkpoint (no full-sheet URL scan)
  - 1,017 files imported, 36,062 unique jobs (deduped by URL)
  - Sheets: Raw, Daily, Companies, Roles, Market, Dashboard, Charts, Weekly
  - Daily trigger at 07:00 via `setupTrigger()`
- **Title classification** (`classifyTitle`): maps job titles to 20 standard categories
  using keyword matching (English + Hebrew) + `DEPT_MAP` exact-match lookup.
  Applied via `reclassifyRaw()` to all 36K rows; reduced dept count from 473 → 34.
- **Data cleaning**: LinkedIn URL truncation, company artifact removal (`cleanCompany()`),
  `workplace_type` normalisation (`normaliseWorkplace()`).
- **Analytics sheets**:
  - `Market`: dept × month pivot with MoM % colour-coded
  - `Companies`: hiring_status (NEW/GROWING/ACTIVE/SLOWING/STOPPED) with colour coding
  - `Dashboard`: KPI + 4 live QUERY formula tables (growing/new/stopped companies, dept trends)
  - `Charts`: 5 built-in Google Charts (line trend, Apr vs May bar, top companies, workplace pie, sources)
  - `Weekly`: last 7 days snapshot with WoW %, by dept/source/company, top 50 jobs table
- **BACKLOG items added**: role filter expansion in frontend, workplace_type normalisation in scrapers

### 2026-06-06 (session 3)
- **`first_seen` date preservation** — implemented `load_first_seen()` helper in scrapers:
  - Root cause: sources without a published `date_posted` were writing `TODAY` on every run,
    causing all their jobs to appear in the "Today" filter daily even when not new.
  - Fix: on each run, scraper reads the previous day's CSV and preserves the original
    discovery date for existing jobs; only truly new jobs get today's date.
  - `load_first_seen(pattern, key_field)` added to **`fetch_jobs.py`** (shared helper):
    - `run_weizmann` — key: URL → `weizmann_jobs_*.csv`
    - `run_technion` — key: URL → `technion_jobs_*.csv`
    - `run_leumit` — key: URL → `leumit_jobs_*.csv`
    - `run_movement` — key: URL → `movement_jobs_*.csv`
    - `run_innovation_israel` — key: URL → `innovation_israel_jobs_*.csv`
    - `run_bgu` — key: title (all BGU jobs share one listing URL) → `bgu_jobs_*.csv`
  - Standalone `load_first_seen()` added to **`fetch_maccabi.py`** — key: URL → `maccabi_jobs_*.csv`
  - **Not patched** (already have real publication dates from API):
    Clalit, Meuhedet (`JobTimeSortAttr`), Ichilov (`activationDate`), BAR (`activationDate`)
  - Fallback logic: if yesterday's file is absent, uses the most recent available CSV;
    if no previous CSV exists at all, all jobs get today's date (safe first-run behaviour)
