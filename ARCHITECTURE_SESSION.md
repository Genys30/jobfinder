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
