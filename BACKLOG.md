# JobFinder · Backlog

Items discovered during the May 2026 refactor session that were intentionally deferred.

---

## 🔴 High Priority

### Missing scrapers — universities & advisory firms show "no file yet"
These sources have a loader in `index.html` and a slot in the data bar, but no scraper
currently writes their CSV. They were populated in the past, so historical data exists
on Google Drive, but the scrapers are gone or were never committed.

**Sources with no working scraper:**
- Advisory: KPMG (`kpmg_jobs_*`) — deferred: site redesigned 2026, part of roles now go through Comeet (`somekhchaikin` token). Needs its own investigation.

**Done so far:** TAU ✅, Haifa ✅, BAR ✅, Shaare Zedek ✅, Hadassah ✅, Ichilov ✅, GotFriends ✅, HUJI positions ✅, BIS ✅, Joint ✅, Deloitte ✅, EY ✅, Osem ✅ (see resolved items below).

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

### ~~Shaare Zedek + Hadassah hospitals~~ ✅ Resolved 2026-06-03
Both are independent Jerusalem hospitals (NOT part of Clalit), so they need their own
scrapers. Built `fetch_szmc.py` and `fetch_hadassah.py` as standalone Playwright scripts
(same pattern as TAU/Haifa/BAR — local-only, run from `run_fetch.bat`):
- **Shaare Zedek** (`szmc_jobs_*`): HunterHRMS portal `szmc.hunterhrms.com`. JS-rendered, so
  Playwright opens the page, clicks each job category to reveal all jobs, collects job-codes,
  then fetches each job-detail page (`/פרטי-משרה/?jobcode=...`) for description/requirements. ~16 jobs.
- **Hadassah** (`hadassah_jobs_*`): Next.js site `he.hadassah.org.il/wanted/careers/`. Playwright
  collects `a[href*='position-']` links, fetches each for the description. ~51 jobs.

**Root cause of the earlier outage:** these scrapers used to live inside a much larger
`fetch_jobs.py` that also had KPMG/Deloitte/EY/Joint/BAR/BIS Playwright functions. That
big version was never committed to the repo (the repo `fetch_jobs.py` is the leaner 1360-line
one that has none of the Playwright scrapers). So szmc/hadassah CSVs silently stopped after
~mid-May; the site loads only the last 7 days from GitHub, hence "no file yet".

**Key lesson:** Playwright scrapers (szmc, hadassah, and the still-pending
KPMG/Deloitte/EY/Joint/BIS) CANNOT run in GitHub Actions as configured — the workflow only
installs `requests beautifulsoup4`, no Playwright/Chromium. They must run locally via
`run_fetch.bat` where Playwright + Chromium are installed and the Israeli IP isn't blocked.

### ~~Ichilov · GotFriends · HUJI positions~~ ✅ Resolved 2026-06-03 (pure requests)
All three are server-rendered / API-based, so they run with plain `requests` (no Playwright):
- **Ichilov** (`topmatch_jobs_*`, read by `loadIchilov`/`normIchilov`): RedMatch/TopMatch
  candidate API — same platform as Bar-Ilan & Clalit. POST to
  `careers.topmatch.co.il/CandidateAPI/api//position/Search/{GUID}` with Ichilov's affiliate
  GUID `3FC41CB2-A7A8-454A-BC2B-0EDC1A919656`. ~81 jobs. 403 from non-IL IPs.
- **GotFriends** (`gotfriends_jobs_*`): plain HTML at `/jobslobby/{category}/?page=N&total=`,
  10 top-level categories, parses `<h2>` links of depth ≥4. ~3200 jobs (was 0 before).
- **HUJI positions** (`huji_positions_*`): HunterHRMS `huji.hunterhrms.com/search-results/`,
  `.job-wrap` + `label.job-title[for=jobcode]`, details at `/job-details/?jobcode=`. ~17 jobs.

### ~~BIS · Joint · Deloitte · EY~~ ✅ Resolved 2026-06-03
Built as standalone scrapers (BIS/Joint/EY on Playwright; Deloitte on Playwright for its
Load-More). All wired into `run_fetch.bat`:
- **BIS** (`bis_jobs_*`): Wix site `bis.org.il/jobs`, `p.font_2.wixui-rich-text__text` titles.
  company "BIS - אגודת סטודנטים בר-אילן", employer-type stays **public** (student-union job
  board, not academic). ~61 jobs.
- **Joint** (`joint_jobs_*`): `thejoint.org.il/en/career/`, `a[href*='juid']`, detail pages
  for description. company "The Joint (ג'וינט)". ~18 jobs.
- **Deloitte** (`deloitte_jobs_*`): site **redesigned 2026** to `careers.deloitte.co.il/positions/`.
  Jobs are `div.position-row` (`.position-row-title`, `.position-location` "{City}, Israel",
  `.position-interest`=dept, `.position-row-link a`=/position/{id}-en/). Shows 7, then AJAX
  Load More via `a.positions-paginate-load-button` (admin-ajax.php, data-total=82). Playwright
  clicks that exact button until the row count stops growing. ~82 jobs.
- **EY** (`ey_jobs_*`): `ey.co.il/career/`, `a[href*='/open-jobs/']`, opens each detail page,
  Hebrew markers תיאור התפקיד / מה נדרש. ~10 jobs.

### ~~Osem-Nestlé — convert from source to company (option B)~~ ✅ Resolved 2026-06-03
Osem is a **company**, not a source — converted like Movement Group: removed from the data bar
and the source filter, kept its own scraper (`fetch_osem.py`), now displayed in the **company
filter under Private**. Company name stays **Osem-Nestlé**.
- Scraper uses **curl_cffi** (`impersonate=chrome110`) to bypass the Akamai WAF — NOT Playwright.
- Two-phase: list pages `/career/open-positions?page=N` → then each job's detail page for the
  description. Description comes from `div.description_single`; department from the JSON-LD
  `JobPosting.industry`; employment type from `employmentType`. ~44 jobs, all with descriptions.
- index.html: removed `osemStatusText` (data bar), `<option value="osem">` (source filter),
  the `if(activeSrc==='osem')` branch, and the data-bar status writes in `loadOsem`; added
  `'osem':'private'` to the employer-type map and `description: g('description')` to `normOsem`
  so the job pop-up shows the description.

**KPMG still deferred:** careers site redesigned in 2026; general vacancies page errored, and
part of KPMG (Somekh Chaikin) roles route through Comeet (`somekhchaikin` token, e.g.
`comeet.com/jobs/somekhchaikin/...`). Needs a dedicated look — possibly just adding the Comeet
token to the existing `run_comeet` flow rather than a new scraper.

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

The manual local runner now has 22 steps:
1. git pull (with `git reset --hard` + LinkedIn CSV backup/restore)
2. Telegram @biltiformali (`fetch_telegram_biltiformali.py`)
3. Rambam · 4. BGU · 5. Maccabi · 6. MOD
7. Clalit (`fetch_clalit.py`) · 8. TAU (`fetch_tau.py`) · 9. Haifa (`fetch_haifa.py`) · 10. Bar-Ilan (`fetch_bar.py`)
11. Ichilov (`fetch_ichilov.py`) · 12. GotFriends (`fetch_gotfriends.py`) · 13. HUJI positions (`fetch_huji_positions.py`)
14. Shaare Zedek (`fetch_szmc.py`, PW) · 15. Hadassah (`fetch_hadassah.py`, PW)
16. Deloitte (`fetch_deloitte.py`, PW) · 17. EY (`fetch_ey.py`, PW) · 18. BIS (`fetch_bis.py`, PW) · 19. Joint (`fetch_joint.py`, PW)
20. Osem-Nestlé (`fetch_osem.py`, curl_cffi)
21. rclone upload all CSVs to Google Drive (graceful skip if rclone missing)
22. commit + push

Local-only scrapers (run from `run_fetch.bat`, not in GitHub Actions):
`fetch_clalit.py`, `fetch_rambam.py`, `fetch_bgu.py`, `fetch_maccabi.py`,
`fetch_mod_jobs.py`, `fetch_telegram_biltiformali.py`, `fetch_tau.py`,
`fetch_haifa.py`, `fetch_bar.py`, `fetch_ichilov.py`, `fetch_gotfriends.py`,
`fetch_huji_positions.py`, `fetch_szmc.py` (PW), `fetch_hadassah.py` (PW),
`fetch_deloitte.py` (PW), `fetch_ey.py` (PW), `fetch_bis.py` (PW),
`fetch_joint.py` (PW), `fetch_osem.py` (curl_cffi).
`fetch_clalit.py`, `fetch_rambam.py`, `fetch_bgu.py`, `fetch_maccabi.py`,
`fetch_mod_jobs.py`, `fetch_telegram_biltiformali.py`, `fetch_tau.py`,
`fetch_haifa.py`, `fetch_bar.py`, `fetch_szmc.py` (Playwright), `fetch_hadassah.py` (Playwright).

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
