# JobFinder — Architecture & Reference

> Single source of truth for **how the project works and why**.
> Companion to `BACKLOG.md` (which tracks *what to do / what's done*).
> **Update this after every session** — see the Session Log at the bottom.

Live site: <https://genys30.github.io/jobfinder/>
Repo: `Genys30/jobfinder` · Local working copy: `C:\Users\Anna\Desktop\Projects\jobfinder`

---

## 1. Big picture — how data flows

```
  Scrapers (local + CI)                     GitHub repo                Browser
  ─────────────────────                     ───────────                ───────
  fetch_*.py  ──writes──►  source_jobs_YYYY-MM-DD.csv  ──git push──►  index.html
                                   │                                   loads last
                                   └──rclone──► Google Drive            7 days of
                                               (full history)          CSVs at runtime
```

- Each scraper writes a **dated CSV** (`{source}_jobs_YYYY-MM-DD.csv`).
- CSVs are committed to GitHub. The repo keeps roughly the **last 7 days**; older
  files are archived to Google Drive and removed from the repo.
- The site is **static** (`index.html` only). At load time it fetches each source's
  CSVs for the **last 7 days** directly from
  `https://raw.githubusercontent.com/Genys30/jobfinder/main/` (`LI_RAW` in index.html),
  parses them in-browser with PapaParse, and renders the listings.
- **Implication:** if a scraper stops producing fresh CSVs, the site shows "no file
  yet" within ~7 days even though old files still exist on Drive. A stale/empty CSV
  for *today* can also hide yesterday's good data, since loaders favor the newest file.

---

## 2. Where things run — local vs GitHub Actions

There are **two** ways scrapers run:

| Runner | What it runs | Notes |
|---|---|---|
| **GitHub Actions** (nightly) | `fetch_jobs.py` | CI only installs `requests beautifulsoup4` + rclone. **No Playwright/Chromium.** Datacenter IP — many `.il` sites and APIs return 403. |
| **`run_fetch.bat`** (local, Anna's Windows machine) | many standalone `fetch_*.py` | Has Playwright + Chromium installed, and an **Israeli IP** that isn't blocked. This is where all the blocked/JS-heavy sources run. |

**Key rule:** any scraper needing Playwright, `curl_cffi`, or an Israeli IP **must**
run locally via `run_fetch.bat` — it cannot run in GitHub Actions as configured.

---

## 3. Sources — master table

Method legend: **req** = plain requests+BeautifulSoup · **API** = JSON API ·
**PW** = Playwright · **cffi** = curl_cffi (TLS impersonation) · **CI** = also runs in GitHub Actions.

| Source | Scraper | Output CSV | Method | Where | Notes |
|---|---|---|---|---|---|
| LinkedIn | (manual upload) | `linkedin_jobs_*` | — | manual | Uploaded each morning by hand |
| Comeet (many cos) | `fetch_jobs.py run_comeet` | `comeet_jobs_*` | API | CI | Reads `companies.json`; ~168+ companies |
| Greenhouse / Lever / Ashby | `fetch_jobs.py` | per-ATS CSVs | API | CI | From `companies.json` |
| Mitam | `fetch_jobs.py` | `mitam_*` | API | CI | `MITAM_API_KEY` GitHub secret |
| Telegram @biltiformali | `fetch_telegram_biltiformali.py` | `jobs_telegram_*` | API | local | |
| Rambam | (in `fetch_jobs.py` / local) | `rambam_*` | — | local | |
| BGU | `fetch_bgu.py` (+`fetch_bgu_extra.py`) | `bgu_jobs_*` | req | local | 2 sources: Salesforce HR portal (often 0) + bgu.ac.il `div.simple-accordion` pages. WAF blocks CI. |
| Maccabi | `fetch_maccabi.py` | `maccabi_*` | — | local | |
| MOD | `fetch_mod_jobs.py` | `mod_*` | — | local | |
| Clalit | `fetch_clalit.py` | `clalit_jobs_*` | — | local | One CSV holds **all** Clalit + its hospitals; frontend splits by hospital — see §6 |
| TAU | `fetch_tau.py` | `tau_jobs_*` | — | local | |
| Haifa Univ | `fetch_haifa.py` | `haifa_jobs_*` | — | local | |
| Bar-Ilan (BAR) | `fetch_bar.py` | `bar_jobs_*` | API | local | RedMatch/TopMatch API, BIU GUID `D8D6FFC7-31E2-46C1-94B4-985C99B9A913` |
| Ichilov / TASMC | `fetch_ichilov.py` | `topmatch_jobs_*` | API | local | RedMatch/TopMatch API, GUID `3FC41CB2-A7A8-454A-BC2B-0EDC1A919656`. **Note filename is `topmatch_jobs_*`** (read by `normIchilov`). |
| GotFriends | `fetch_gotfriends.py` | `gotfriends_jobs_*` | req | local | `/jobslobby/{cat}/?page=N&total=`, 10 categories, `<h2>` links depth≥4. ~3200 jobs |
| HUJI positions | `fetch_huji_positions.py` | `huji_positions_*` | req | local | HunterHRMS `huji.hunterhrms.com`, `.job-wrap`+`label.job-title[for=jobcode]` |
| HUJI Alumni Career | (`fetch_jobs.py`) | `huji-alumni_*` | — | — | Job board for alumni (multiple employers) → employer-type `public`, in `AGENCY_SOURCES` |
| Shaare Zedek | `fetch_szmc.py` | `szmc_jobs_*` | PW | local | HunterHRMS `szmc.hunterhrms.com`; click categories → jobcodes → detail pages |
| Hadassah | `fetch_hadassah.py` | `hadassah_jobs_*` | PW | local | Next.js `he.hadassah.org.il/wanted/careers/`, `a[href*='position-']` |
| Beilinson | (own loader, reads `clalit_jobs_*`) | — | — | — | **Beilinson == Rabin Medical Center** (the `רבין` rows in Clalit CSV) |
| Soroka | (own loader, reads `clalit_jobs_*`) | — | — | — | `סורוקה` rows in Clalit CSV |
| Deloitte | `fetch_deloitte.py` | `deloitte_jobs_*` | PW | local | Site redesigned 2026 → `careers.deloitte.co.il/positions/`. `div.position-row`; clicks `a.positions-paginate-load-button` until rows stop growing (~82) |
| EY | `fetch_ey.py` | `ey_jobs_*` | PW | local | `ey.co.il/career/`, `a[href*='/open-jobs/']`, detail pages, markers תיאור התפקיד / מה נדרש |
| BIS | `fetch_bis.py` | `bis_jobs_*` | PW | local | Wix `bis.org.il/jobs`, `p.font_2.wixui-rich-text__text`. Student-union board → employer-type **public** |
| Joint (JDC) | `fetch_joint.py` | `joint_jobs_*` | PW | local | `thejoint.org.il/en/career/`, `a[href*='juid']`, detail pages |
| Osem-Nestlé | `fetch_osem.py` | `osem_jobs_*` | cffi | local | **A company, not a source** (see §7). Akamai WAF → curl_cffi `chrome110`. List pages + detail pages (`div.description_single` + JSON-LD `JobPosting`) |
| KPMG | (`run_comeet` via `companies.json`) | `comeet_jobs_*` | API | CI | Routes through **Comeet** as *Somekh Chaikin*: `"comeet": "somekhchaikin/F3.007"` in companies.json. ~52 jobs. No standalone scraper. |

---

## 4. The frontend (`index.html`)

A single static file. Per source it has:

- **`load{Source}()`** — fetches the last 7 days of that source's CSVs from `LI_RAW`,
  parses with PapaParse, fills an in-memory array (e.g. `OSEM_JOBS`, `CL_JOBS`), then
  calls `populateDropdowns()` + `applyFilters()`.
- **`norm{Source}(row, fname)`** — maps a CSV row to the common job object
  (`source, title, company, category, city, url, updated, description, …`).
- **Data bar** — the strip of "Source: N jobs" pills at the top. Each pill is a
  `<span id="{source}StatusText">` plus an entry in the status-map list (`{ id, key, label }`).
- **Source filter** — `<option value="{source}">` entries in the SOURCES dropdown.
- **Employer-type map** — assigns each source to `private` / `public` / `academic` /
  `nonprofit` (the 4 filter options). There is **no "Advisory" filter type** — "Advisory"
  is only a textual grouping in the info block. KPMG/Deloitte/EY are `private`.
- **`AGENCY_SOURCES`** = `{'gf','huji-alumni'}` — job boards/agencies excluded from the
  "real employer" counts.
- **Job pop-up** reads `r.description`; a norm function must pass `description` for the
  pop-up to show anything.

`LI_RAW = https://raw.githubusercontent.com/Genys30/jobfinder/main/`

---

## 5. `companies.json` — the ATS registry

Array of company objects. Schema:

```json
{ "name": "...", "greenhouse": null, "lever": null, "comeet": "slug/UID",
  "ashby": null, "workable": null, "breezy": null, "careers_url": null,
  "added_by": "...", "added_date": "YYYY-MM-DD", "active": true }
```

- A company is scraped via whichever ATS field is non-null.
- **Comeet format = `slug/company_uid`** (e.g. `somekhchaikin/F3.007`). `run_comeet`
  splits on `/`, then calls `comeet_token(slug, uid)` and the Comeet API
  `https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token=...`.
- `"active": false` freezes a source (blocked/inactive) without deleting it.

---

## 6. Clalit hospital bucketing (important gotcha)

`clalit_jobs_*.csv` contains **all** Clalit district roles **and** all its hospitals in
one file. The CSV has **no `source` column** — the hospital name lives in **`company`**
(Hebrew). The frontend's `loadClalit()` must split rows into hospital buckets using a
`hospitalBy(company)` helper that matches the Hebrew name:

| Hebrew in `company` | Bucket |
|---|---|
| מאיר | meir |
| קפלן | kaplan |
| שניידר | schneider |
| יוספטל | yoseftal |
| העמק | emek |
| לוינשטיין | loewenstein |
| כרמל | carmel |
| רבין | **null** (dropped — Beilinson loader shows these) |
| סורוקה | **null** (dropped — Soroka loader shows these) |
| מחוז… / הנהלה (districts/HQ) | clalit |

**Failure mode (seen twice):** if the code buckets by `r.source` instead of
`hospitalBy(r.company)`, every row falls into Clalit (it shows ~557, hospitals show 0).
The fix is the `hospitalBy` helper. **Rabin** is intentionally hidden from the data bar
and filter because Rabin == Beilinson (shown under Beilinson).

---

## 7. Osem-Nestlé — "company, not source" pattern (option B)

Some entities should appear in the **company filter** (under their employer type), not as
a top-level source in the data bar. Movement Group and Osem-Nestlé use this pattern:

- Keep the scraper + its `{name}_jobs_*.csv`.
- `norm{X}` fills its array (e.g. `OSEM_JOBS`) which is merged into the general pool.
- **Remove** from: data bar status row, source filter `<option>`, status-map list, and any
  `if(activeSrc==='{x}')` branch. `load{X}` keeps only the array-fill (no status writes).
- **Add** `'{x}':'private'` (or correct type) to the employer-type map.
- Make sure `norm{X}` passes `description` so the job pop-up works.

---

## 8. `run_fetch.bat` — the local nightly runner (23 steps)

1. git pull (with `git reset --hard` + LinkedIn CSV backup/restore)
2. Telegram @biltiformali · 3. Rambam · 4. BGU · 5. Maccabi · 6. MOD
7. Clalit · 8. TAU · 9. Haifa · 10. Bar-Ilan
11. Ichilov · 12. GotFriends · 13. HUJI positions
14. Shaare Zedek (PW) · 15. Hadassah (PW)
16. Deloitte (PW) · 17. EY (PW) · 18. BIS (PW) · 19. Joint (PW)
20. Osem-Nestlé (curl_cffi) · 21. Teva Pharmaceuticals (req)
22. `fetch_jobs.py` — ATS sources (Comeet incl. KPMG, Greenhouse, Lever, Ashby) + local sources
23. rclone upload all CSVs → Google Drive
+ commit + push

Each fetch step uses `if errorlevel 1 ( WARNING … continuing anyway )` so one failure
doesn't abort the rest.

---

## 9. Infrastructure

- **Google Drive archive**: rclone OAuth, account `sncentral.data@gmail.com`, folder
  `jobfinder-data` (`RCLONE_TOKEN` GitHub secret). Repo keeps ~7 days; Drive keeps full
  history. The **site loads from GitHub, not Drive.**
- **GitHub Actions** workflow `.github/workflows/fetch_jobs.yml`: installs only
  `requests beautifulsoup4` + rclone. Runs `fetch_jobs.py` nightly.
- **GitHub Pages**: serves the static site from `main`.
- **Secrets**: `MITAM_API_KEY`, `RCLONE_TOKEN`.

---

## 10. Process & conventions (how we work)

- **SDD workflow**: Audit → Specification → **Confirmation** → Implementation →
  Verification → Backlog update.
- **Ask first, get permission before acting.** Don't make silent assumptions or
  overwrite existing work without confirming. (A silent overwrite cost the Clalit
  hospital fix twice.)
- **When editing `index.html`, pull the LIVE version from GitHub first** — don't assume
  an uploaded copy is the latest. The live file accumulates fixes between sessions.
- **Delivery**: Anna downloads files from Claude's outputs and runs terminal commands
  directly (does not git-pull Claude's changes). Replies to Anna in **Russian**; all code
  and docs in **English**.
- **Per-scraper deploy**:
  ```
  git add -f {source}_jobs_YYYY-MM-DD.csv
  git add fetch_{source}.py run_fetch.bat
  git commit -m "..."
  git pull --rebase origin main
  git push
  ```
- **Git conflict recovery** (nightly Actions commits CSVs, conflicting with local):
  `git stash → git pull --rebase → git stash pop → git push`.
- **Verify CSV contents** via `curl` on the raw GitHub URL (`tail`) — the script's
  terminal summary doesn't prove the columns were written.
- **Syntax-check** scrapers after edits: `python3 -c "import ast; ast.parse(open('f.py').read())"`.
- A scraper tested with a single-company call (e.g. `run_comeet([{...}], {})`) will
  **overwrite that source's CSV with only that company** — don't commit such a partial CSV;
  the full nightly run regenerates it.
- **Keep this doc current.** At the end of every session, update `ARCHITECTURE.md` — add a
  Session-log entry (§11) and revise any section the session changed. Claude proposes this
  update by default at session end (same as it does for `BACKLOG.md`).

---

## 11. Session log

Newest first. Keep entries short — details go in `BACKLOG.md`.

### 2026-06-03
- Restored/added scrapers: TAU, Haifa, BAR, Shaare Zedek (16), Hadassah (51), Ichilov (81),
  GotFriends (3213), HUJI positions (17), BIS (61), Joint (18), Deloitte (82), EY (10).
- Osem-Nestlé converted from source → **company** (option B); scraper now fetches
  descriptions (curl_cffi + detail pages) so the pop-up works.
- KPMG resolved via **Comeet** (`somekhchaikin/F3.007` in companies.json) — no new scraper.
- Fixed Clalit **hospital bucketing** (`hospitalBy(company)`) — it had regressed to bucketing
  by the non-existent `source` column, dumping everything into Clalit.
- **Rabin** hidden from data bar + source filter (Rabin == Beilinson).
- BGU re-run after a transient empty CSV (Salesforce gave 0; bgu.ac.il pages gave 9).
- `run_fetch.bat` grown to **22 steps**.
- Created this `ARCHITECTURE.md`.

### 2026-06-04 / 2026-06-05
- **Teva Pharmaceuticals** added as a new source (`fetch_teva.py`, SAP SuccessFactors,
  req+BeautifulSoup). Follows "company not source" pattern (§7) — appears in company
  filter under Private type. Local-only (careers.teva blocks non-Israeli IPs).
  `run_fetch.bat` grown to **23 steps** (step 21: Teva, step 22: fetch_jobs.py).
- **Google Sheets Analytics Dashboard** built from scratch (`Code.gs`, ~1200 lines).
  Reads all job CSVs from Google Drive via Apps Script. 1,017 files, 36,062 unique jobs.
  8 sheets: Raw, Daily, Companies, Roles, Market, Dashboard, Charts, Weekly.
  Daily trigger at 07:00 via `setupTrigger()`. Title classification (`classifyTitle`)
  maps titles to 20 standard categories; reduced dept count from 473 → 34.
  Spreadsheet: Jobfinder-Analytics (sotnik@gmail.com).

### 2026-06-06
- **`first_seen` date preservation** implemented in scrapers.
  Sources without a published `date_posted` were writing `TODAY` on every run, causing all
  their jobs to appear in the "Today" filter daily even when not new.
- Added `load_first_seen(pattern, key_field)` helper to **`fetch_jobs.py`**: reads the
  previous day's CSV, returns `{key: date}` dict; only truly new jobs get today's date.
  Patched: `run_weizmann`, `run_technion`, `run_leumit`, `run_movement`,
  `run_innovation_israel` (key: URL); `run_bgu` (key: title — all BGU jobs share one URL).
- Added standalone `load_first_seen()` to **`fetch_maccabi.py`** (key: URL).
- Not patched (already have real dates from API): Clalit, Meuhedet, Ichilov, BAR.

### 2026-06-07
- **Data bar filter-awareness fixed** (`index.html`): Maccabi, Leumit, Meuhedet, Soroka,
  Beilinson, and all Clalit hospitals were hardcoding `X jobs` bold regardless of active
  filters. Fixed by adding these sources to `DATABAR_SOURCES` array and removing all
  hardcoded `innerHTML` writes from their `load*()` functions — `updateDatabar()` now
  handles them uniformly. When a filter (e.g. Today) is active, data bar shows
  `filtered / total` for every source.
- **`first_seen` extended to all remaining local scrapers**: `fetch_tau.py`,
  `fetch_haifa.py`, `fetch_rambam.py`, `fetch_deloitte.py`, `fetch_ey.py`, `fetch_bis.py`,
  `fetch_huji_positions.py`, `fetch_joint.py`, `fetch_szmc.py`, `fetch_hadassah.py`,
  `fetch_gotfriends.py`. Each now reads the previous day's CSV on startup and preserves
  original discovery dates for recurring jobs. Effect visible from the next bat run.

### 2026-06-06 (session 3 — Google Sheets Analytics extended)
- **Charts sheet** added: 5 Google Charts (dept trend last 6 months, Apr vs May bar,
  top 20 companies, workplace pie, top 15 sources by last 30d).
- **Weekly sheet** added: WoW %, by dept/source/company, top 50 jobs table.
- **Date parsing fixed**: `parseDateSafe()` now handles both Date objects (from Sheets)
  and YYYY-MM-DD strings — fixes `last30=0` bug in Dashboard KPIs.
- **Title classifier** improved via `debugOther()` (4 rounds): Other reduced 10,153 → 5,468.
  Added `DEPT_MAP` exact-match lookup, Hebrew dept normalisation, garbage detection.
  `reclassifyRaw()` / `continueReclassify()` added for retroactive reclassification.
- **Company filtering** added: `shouldExcludeCompany()` with explicit `RECRUITING_COMPANIES`
  blacklist, logo/garbage pattern detection, job-title detection, recruiting keyword check.
  `cleanCompany()` strips LinkedIn multiline artifacts from company field.
- `normaliseWorkplace()` consolidates variants → 7 standard values.
- Code.gs grown to **~1600 lines**. New §12 added to this doc.

---

## 12. Google Sheets Analytics Dashboard

A private analytics tool reading all historical CSVs from Google Drive via Apps Script.

- **Spreadsheet:** Jobfinder-Analytics (sotnik@gmail.com)
- **Drive folder:** `jobfinder-data` shared from sncentral.data@gmail.com
- **Script:** `Code.gs` (~1600 lines), Apps Script bound to the spreadsheet
- **Trigger:** daily at 07:00 via `setupTrigger()` → runs `importIncremental`

**Sheets:**

| Sheet | Contents |
|---|---|
| Raw | Every unique job ever seen (36K+), deduped by URL |
| Daily | Jobs per source per day — use for trend charts |
| Companies | Real employers only (recruiters/agencies filtered out) with hiring_status |
| Roles | All departments ranked + workplace type breakdown |
| Market | Dept × Month pivot with MoM % — main research table |
| Dashboard | KPI summary + 4 live QUERY formula tables |
| Charts | 5 Google Charts (dept trend, Apr vs May, top companies, workplace pie, sources) |
| Weekly | Last 7 days: WoW %, by dept/source/company, top 50 jobs |

**Key functions:**
- `importIncremental()` — daily delta import (new files only)
- `resetAndImport()` / `continueImport()` — full reload from scratch
- `reclassifyRaw()` / `continueReclassify()` — re-run title classification on all Raw rows
- `buildCharts()`, `buildWeekly()` — rebuild individual sheets manually
- `debugOther()` — show top titles in "Other" category (helps improve classifier)

**Title classification (`classifyTitle` + `DEPT_MAP`):**
Maps job title → one of 20+ standard categories using keyword matching (EN + HE) and
exact-match lookup table. Applied at parse time and via `reclassifyRaw()`.

**Company filtering (`shouldExcludeCompany`):**
Companies sheet excludes: explicit recruiter blacklist (`RECRUITING_COMPANIES`), logo/image
filenames, names that look like job titles (2+ keywords like "engineer"/"developer"),
names containing recruiting keywords (השמה, staffing, headhunt…), names outside 2–80 chars.
To add a new recruiter: `"Company Name": true` in `RECRUITING_COMPANIES` in Code.gs.

**Important:** the site loads data from GitHub (not Drive). This dashboard is separate
from the live site — it reads the full Drive archive independently.

