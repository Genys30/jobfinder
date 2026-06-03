# JobFinder · Backlog

Items discovered during the May 2026 refactor session that were intentionally deferred.

---

## 🔴 High Priority

### Missing scrapers — universities & advisory firms show "no file yet"
These sources have a loader in `index.html` and a slot in the data bar, but no scraper
currently writes their CSV. They were populated in the past, so historical data exists
on Google Drive, but the scrapers are gone or were never committed.

**Sources with no working scraper:**
- Universities: HUJI positions (`huji_positions_*`)
- Advisory: KPMG (`kpmg_jobs_*`), Deloitte (`deloitte_jobs_*`), EY (`ey_jobs_*`), BIS (`bis_jobs_*`)
- NGO / recruiters: Joint (`joint_jobs_*`), GotFriends (`gotfriends_jobs_*`), TopMatch (`topmatch_jobs_*`)
- Hospitals: Hadassah (`hadassah_jobs_*`), Shaare Zedek (`szmc_jobs_*`)

**Done so far:** TAU ✅, Haifa ✅, BAR ✅ (see resolved items below).

**Action:** Build or restore one scraper per source, one at a time. Each must write the
exact filename the loader expects (verified against `index.html`). Follow SDD: audit the
career page, confirm column mapping, implement, verify on the live site.

**Note:** GotFriends is already called in the nightly workflow but produces no data —
needs debugging, not a new scraper.

### ~~Lever — 5 companies returning 404~~ ✅ Resolved 2026-05-30
- Contrast Security Israel → no open positions → `active: false`
- CYE → no open positions → `active: false`
- Digital Turbine → moved to Workday (not supported) → `active: false`
- Sauce → Lever 403 blocked → `active: false`
- Vault Platform → no open positions → `active: false`

### ~~HUJI Alumni Career — wrong output filename~~ ✅ Resolved 2026-06-02
`fetch_jobs.py` wrote `huji_jobs_*` but the site loader expects `huji_alumni_jobs_*`.
Renamed the output in `fetch_jobs.py` (line ~748). HUJI Alumni Career now shows ~300 jobs.

### ~~Clalit scraper not running~~ ✅ Resolved 2026-06-02
`fetch_clalit.py` worked but was not called by any runner, so Clalit went stale after
~2026-05-30. Added `fetch_clalit.py` to `run_fetch.bat`. Clalit now shows ~557 jobs.

### ~~TAU scraper~~ ✅ Resolved 2026-06-02
Built `fetch_tau.py`. Source: Hebrew page `tau.ac.il/positions?qt-jobs_tabs=0` (admin)
and `=1` (academic), jobs rendered in HTML as `table.views-table`. Writes `tau_jobs_*`.
Wired into `run_fetch.bat`. ~29 jobs. Note: 403 from non-Israeli IPs, runs fine locally.

### ~~Haifa University scraper~~ ✅ Resolved 2026-06-02
Built `fetch_haifa.py`. Source: `hr.haifa.ac.il/דרושים/` (WordPress/Elementor), jobs are
`<a>` links matching `hr.haifa.ac.il/{number}-`. Writes `haifa_jobs_*`. Wired into
`run_fetch.bat`. ~20 jobs. Also 403 from non-Israeli IPs.

### ~~Bar-Ilan (BAR) scraper~~ ✅ Resolved 2026-06-03
Built `fetch_bar.py`. The official HR portal is behind employee login, so the scraper
uses the RedMatch/TopMatch candidate API that powers `careers.topmatch.co.il/biu/`:
`POST .../CandidateAPI/api//position/Search/{AFFILIATE_GUID}` with body
`{"KeyWords":"","CategoryId":[],"countryId":2,"cityId":[]}`. The GUID
`D8D6FFC7-31E2-46C1-94B4-985C99B9A913` is BIU's affiliate ID. Response has a `positions[]`
array (compPositionID, jobTitleText, displayLocation, fieldDesc, description HTML,
scheduleExpirationDate). Writes `bar_jobs_*`. Wired into `run_fetch.bat`. ~13 jobs.
403 from non-Israeli IPs. (RedMatch is reusable for any TopMatch affiliate — just swap the GUID.)

### ~~Clalit medical centers showing 0 jobs~~ ✅ Resolved 2026-06-03
The data bar listed Rabin, Meir, Kaplan, Schneider, Yoseftal, Emek, Loewenstein, Carmel —
all stuck at "0 jobs". Root cause: `loadClalit()` split rows into hospital buckets by a
`r.source` field that **does not exist** in `clalit_jobs_*.csv` (its columns are
title, company, location, date, url, department, workplace_type, description). So every
row fell into the general Clalit bucket. The hospital name actually lives in `company`
(Hebrew, e.g. `מרכז רפואי מאיר`). Fixed `loadClalit()` to route by a `hospitalBy(company)`
substring match. Rows for `רבין` and `סורוקה` are dropped from the Clalit bucket because
Beilinson and Soroka have their own dedicated loaders reading the same file (avoids double
counting). Result: Clalit ~333 (district roles only), Meir 40, Kaplan 35, Yoseftal 24,
Schneider 23, Emek 16, Loewenstein 14, Carmel 8; Beilinson 38 / Soroka 26 unchanged.

**Note:** Beilinson == Rabin Medical Center (the `רבין` rows). Beilinson's loader already
surfaces those, which is why Rabin's own bucket is intentionally left empty.

---

## 📦 Google Drive archive (set up 2026-06-02)

CSV history is now archived to Google Drive instead of bloating the repo. The repo keeps
only the last 7 days of `*_jobs_*` files; the full history lives on Drive.

- **Account:** sncentral.data@gmail.com
- **Folder:** `jobfinder-data` (ID `18_hQPxPgpkbHwFoevdDgSq2yCAeEw5LU`)
- **Nightly upload:** GitHub Actions installs rclone and uploads via `RCLONE_TOKEN` secret
- **Manual upload:** `run_fetch.bat` step [11/12] uploads all CSVs via local rclone config
- **Upload pattern:** `*.csv` (covers `*_jobs_*`, `jobs_telegram_*`, `huji_positions_*`, etc.)
- rclone only transfers new/changed files, so daily runs are cheap

**Known limitation:** A Google service-account cannot upload to a personal Drive (no
storage quota). That's why we use rclone with OAuth instead of the service-account JSON.

**Orphan scrapers identified (do NOT wire into runners — duplicates):**
- `fetch_huji.py` → duplicate of HUJI logic in `fetch_jobs.py`
- `fetch_osem.py` → site has no `osem_jobs_*` loader
- `fetch_bgu_extra.py` → duplicate of `fetch_bgu.py`
- `fetch_jobs_from_companies.py` → duplicate of `fetch_jobs.py` (Comeet parse fails on UTF-8 BOM)
- `fetch_mitam.py`, `fetch_weizmann.py` → superseded by `fetch_jobs.py`

**Future:** Google Sheets analytics dashboard reading from the Drive archive
(trends over time, period-over-period comparison, top companies/roles).

---

## 🛠 `run_fetch.bat` step reference (as of 2026-06-03)

The manual local runner now has 12 steps:
1. git pull (with `git reset --hard` + LinkedIn CSV backup/restore)
2. Telegram @biltiformali (`fetch_telegram_biltiformali.py`)
3. Rambam · 4. BGU · 5. Maccabi · 6. MOD
7. Clalit (`fetch_clalit.py`) · 8. TAU (`fetch_tau.py`) · 9. Haifa (`fetch_haifa.py`) · 10. Bar-Ilan (`fetch_bar.py`)
11. rclone upload all CSVs to Google Drive (graceful skip if rclone missing)
12. commit + push

Local-only scrapers (run from `run_fetch.bat`, not in GitHub Actions):
`fetch_clalit.py`, `fetch_rambam.py`, `fetch_bgu.py`, `fetch_maccabi.py`,
`fetch_mod_jobs.py`, `fetch_telegram_biltiformali.py`, `fetch_tau.py`,
`fetch_haifa.py`, `fetch_bar.py`.

---

## 🟡 Medium Priority

### LinkedIn — manual upload every morning
Currently scraped manually each morning and uploaded as `linkedin_jobs_YYYY-MM-DD.csv`.

**Action:** Investigate automation options. LinkedIn blocks most scrapers, but tools like Apify or a browser extension could help. Low priority until a reliable solution is found.

### Workable / Breezy — frozen sources, revisit in ~1 month
Both sources were frozen (`active: false`) because their APIs return 403 from GitHub Actions.

**Action:** Check in ~1 month whether the APIs have opened up. If yes, set `active: true` in `companies.json` for the relevant companies.

Companies frozen:
- **Workable:** Atera Networks, BigPanda, Cloudinary, Healthy.io, Innovid, Papaya Global, Poptin, SolarEdge Technologies, Trustmi, Vayyar Imaging
- **Breezy:** Ayyeka, Dalet, Descope Technologies, Insights.US, Lynx.MD

---

## 🟢 Low Priority

### Ashby — only 2 companies tracked
Currently tracking: Datawizz.AI, Nexxen.

**Action:** Find more Israeli companies using Ashby ATS and add them to `companies.json`.

### BGU — intermittently returns 0 jobs
The BGU scraper works correctly but the university sometimes has no open positions.

**Action:** Monitor over time. No fix needed unless it stays at 0 for weeks.

### Node.js 20 deprecation warning in GitHub Actions
Actions emit a warning about Node.js 20 being deprecated (forced to Node.js 24 from June 16, 2026).

**Action:** Update workflow versions in `.github/workflows/fetch_jobs.yml`:
- `actions/checkout@v4` → `actions/checkout@v4.2.2`
- `actions/setup-python@v5` → `actions/setup-python@v5.6.0`

---

## 💡 Ideas (no timeline)

- **Email alerts** — notify when a source fails for 3+ consecutive days
- **Company health check** — weekly script that pings each ATS token and flags dead ones
- **Salary data** — enrich jobs with salary ranges where available
- **Duplicate detection** — same job appearing via LinkedIn and Comeet

---

*Last updated: 2026-06-03*
