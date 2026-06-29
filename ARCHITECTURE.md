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
| Afeka College | `fetch_afeka.py` | `afeka_jobs_*` | req | local | Engineering college's **own** positions (employer-type `academic`), NOT the Afeka Jobs student portal. Umbraco CMS, server-rendered Bootstrap accordion `div.accordion-item` (title in `.accordion-header button`, body in `.accordion-collapse`). Both tabs (admin staff / academic faculty) in static HTML. No per-job URL → `first_seen` keyed by **title** (BGU pattern). Frontend dedup by `title+url`. Job-marker filter drops the events accordion. |
| SCE (Sami Shamoon) | `fetch_sce.py` | `sce_jobs_*` | PW | local | Engineering college's **own** positions (employer-type `academic`). Three HR "wanted" sub-pages (admin / academic / research). **WAF JS-challenge**: plain requests AND curl_cffi both 403 → **Playwright** (one shared context, warm-up on the hub solves the challenge once). Server-rendered (no JS rendering needed) but the challenge requires a real browser. **Mixed link shapes**: admin jobs → external **CIVI** ATS (`app.civi.co.il/promo/id=N&src=M` — keep `src`, it's required or CIVI 404s); academic/research → internal SCE detail pages (`/wanted/{section}/{slug}`). Real per-job URLs → `first_seen`/dedup by **url**. Site emits doubled-domain hrefs (`/www.sce.ac.il/...`) — normalized. v1: no descriptions. |
| Braude (ORT) | `fetch_braude.py` | `braude_jobs_*` | req | local | Engineering college's **own** positions (employer-type `academic`), Karmiel. WordPress, server-rendered, **no WAF** → req+BeautifulSoup (like Afeka). Foundation accordion: `li.accordion-item` → `a.accordion-title` (title) + `div.accordion-content` (description, **inline & rich** — pop-up works). One page, two sections משרות מנהליות / משרות אקדמיות → `department` by nearest preceding section heading (title-keyword fallback). No per-job URL (apply by email) → `first_seen` by **title** (Afeka/BGU pattern), frontend dedup by `title+url`. Job-marker filter guards non-job accordions. |
| HIT (Holon) | `fetch_hit.py` | `hit_jobs_*` | cffi | local | Engineering institute's **own** positions (employer-type `academic`), Holon. WordPress, server-rendered, but behind a **Sucuri/SPD gateway** that 302-loops plain requests to `//abuse.spd.co.il` → **curl_cffi** `chrome110` (like Osem; warm-up on home page + retries). Bootstrap accordion in **two tabs**: `div#JOB_accordion0` → admin, `div#JOB_accordion1` → academic; each job `div.accordion-item` → `div.accordion_title` (title) + `div.accordion-body` (description, **inline & rich** — pop-up works). `department` by tab id. **Per-job dedup by `#collapseN`**: jobs have no real URL, and two distinct postdocs can share the title "משרת פוסטדוק | Postdoctoral Position" → each item's unique `#collapseN` id is appended to the page URL as a fragment so they stay separate (`first_seen`/dedup by url; frontend dedup `title+url`). `clean_title` strips the "למכון טכנולוגי חולון" prefix. |
| Azrieli (JCE) | `fetch_azrieli.py` | `azrieli_jobs_*` | cffi | local | Azrieli College of Engineering Jerusalem (JCE)'s **own** positions (employer-type `academic`), Jerusalem. WordPress (theme `roots-mipo`), server-rendered, but plain requests get a **403 block page** → **curl_cffi** `chrome110` (like Osem/HIT; warm-up on home + retries). Custom accordion in **two sections**: `div#academic-staff` → academic, `div#administrative-staff` → admin; each job `div.unit` → `div.unit_name > h3` (title) + `div.unit_content` (description, **inline & rich** — pop-up works). `department` by section id. No per-job URL (apply by email) → `first_seen` by **title** (Afeka/BGU pattern), frontend dedup `title+url`. URL is "possitions" (sic). |
| Shenkar | `fetch_shenkar.py` | `shenkar_jobs_*` | req | local | Shenkar College of Engineering & Design's **own** positions (employer-type `academic`), Ramat Gan — the 6th engineering/tech college. WordPress (WPML), **no WAF** → req+BS4. **Structurally different**: NOT an accordion — a flat list of links, each pointing to an **external Google Docs/Drive** doc with the full text. Job links identified by href (`docs.google.com`/`drive.google.com`) + a title marker (דרוש/קול קורא/מרצה). **No inline descriptions** (body lives in the external doc; v1 leaves `description` empty — pop-up is blank). Links ARE real per-job URLs → `first_seen`/dedup by **url** (like SCE). All postings are faculty roles → `department=academic_faculty`. `clean_title` strips a trailing posting-date and fixes "דרוש/ ה" → "דרוש/ה". Small list (~6), may include older postings the college still lists. |
| Sapir | `fetch_sapir.py` | `sapir_jobs_*` | req→cffi | local | Sapir Academic College's **own** positions (employer-type `academic`), Sderot — **1st general (non-engineering) college**. Page `sapir.ac.il/hr/wanted` redirects to a **CIVI ATS feed** (`app.civi.co.il/promos/id=NLY65YEJTW&src=13586`), scraped directly. Each job is a `div.thumb-content` card → `.title` + `.descr` (description **inline & rich** → pop-up works); the job id is in the `openPromo(event,<ID>,13586,1)` onclick → per-job URL `app.civi.co.il/promo/id=<ID>&src=13586` (real per-job URL → `first_seen`/dedup by **url**, like SCE). **Pagination:** CIVI uses `&p=N` (20/page; `?rows=` is ignored) — loop pages until one yields no new cards. `department` inferred from title keywords (חבר סגל/מרצה/מנחה/רקטור/דיקן → academic, else admin) since the feed has no section split. Scope = academic **+ admin** (Anna's choice for general colleges). ~21 jobs, mostly admin. |
| Emek Yezreel (YVC) | `fetch_yvc.py` | `yvc_jobs_*` | req | local | Max Stern Yezreel Valley College's **own** positions (employer-type `academic`), Yezreel Valley — 2nd general college. WordPress (theme `emek`), **no WAF** → req+BS4. **Source key is `yvc` (not `emek`)** because `EMEK_JOBS` already exists for HaEmek Medical Center (the Afula hospital) — avoids the collision. Single accordion: `section.q-and-a` → `div.question-item` → `a.question-link span` (toggle) + `div.answer` (body). **Duplicate-title gotcha (like HIT):** toggle text repeats; the distinguishing course name is in the body's first `<p>` ("…לקורס: COURSE") → the title is **enriched with the course name** to make it unique (the `#questionN` anchor is sequential/unstable, so not used as a key). No per-job URL (apply by email) → `first_seen`/dedup by enriched **title** (Afeka/Braude pattern). `department` by keyword. ~5 jobs, all academic course positions. |
| Tel-Hai | `fetch_telhai.py` | `telhai_jobs_*` | req | local | Tel-Hai Academic College's **own** positions (employer-type `academic`), Galilee — 3rd general college. **Drupal** (Olivero theme, Views), server-rendered, **no WAF** → req+BS4 (web_fetch is bot-blocked, but plain requests works from an Israeli IP). **Two pages, department by page**: `/jobs` → academic_faculty, `/jobs-2` → admin_staff. Each is a Views **table**: `tr` → `td.views-field-title a[href^="/position/"]` (real per-job URL), plus metadata cells (`field-job-scope`, `field-availability`, `field-exteral-internal` [sic], `field-submission-deadline`). **External-only filter** (Anna's choice): rows where the exteral-internal cell says פנימית (internal) are skipped — internal postings aren't useful in a public feed. `position_type` derived from the scope cell (חצי משרה → part_time, חל"ד → maternity_cover). Real per-job URLs → `first_seen`/dedup by **url**. v1 does not fetch the `/position/` detail pages — description is built from the row's metadata. ~27 jobs (7 academic + 20 admin). |
| Ruppin | `fetch_ruppin.py` | `ruppin_jobs_*` | PW | local | Ruppin Academic Center's **own** positions (employer-type `academic`), Emek Hefer — **4th & final general college**. Behind an **Imperva WAF (status 247)** — plain requests AND curl_cffi both blocked → **non-headless Playwright** (`headless=False` + `--disable-blink-features=AutomationControlled`); LOCAL-ONLY (cannot run in CI). **Two pages, department by page**: `/administration/academic-staff-required/` → academic_faculty, `/administration/administrative-staff-required/` → admin_staff. Each job is a `div.card` → `.card-header` (title) + `.card-body` (body). **Mixed apply shapes**: academic → apply by **email**, no per-job URL (`url` = page URL, inline description from the card body); admin → per-job **PDF** (מכרז) link (`url` = PDF, description empty). Frontend dedups **uniformly by title+url** (admin urls differ; academic share the page url but titles differ — no mixed-key code needed). `clean_title` strips zero-width + bidi (RLM/LRM) marks because academic is **title-keyed**. `position_type` = `maternity_cover` if title has חל"ד, else ''. External-only filter (`פנימית` skipped) — no-op now, stub for future. ~17 jobs (9 academic + 8 admin). |
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
| NAMER (נמ"ר) | `fetch_namer.py` | `namer_jobs_*` | API | local | **National local-authority tenders** (מכרזי כוח אדם, רשויות מקומיות) — Ministry of Interior's central system. employer-type **`public`**. One feed → hundreds of authorities (~580 open). Angular SPA backed by an Azure **APIM gateway** (anonymous, public key): `GET …/namer-anonymous/v1/api/ManageMichrazim/GetAllSiteMichrazim/?basePage=<json>` + header `Ocp-Apim-Subscription-Key`. **`basePage` filters MUST be `null`, not `[]`** (empty arrays NRE the server); `page:{Number,SumItem}` paginates (0-based, stop on empty page). Key is re-derived from the site bundle at runtime (32-hex), with a hardcoded fallback. Real publish date (`ptichatMichrazDate`) → no first_seen. Per-job url `namerz.moin.gov.il/showexternal/{misparAsmachta}/{oid}`; **dedup by `misparAsmachta`** (oid is not unique alone). Open only (`kodStatus=0`/`פתוח`, skip `sibatBitul`/`sibatDchiya`). Title: `shemTafkid`, but ~27% are literally **"אחר"** → for those a per-michraz **detail fetch** (`Michraz/GetSiteMichraz/{asmachta}/{oid}`, GET, singular "Michraz") supplies the real role name **`teurMichraz`** (throttled+cached, 'אחר' rows only); on failure falls back to `tchumMiktzoi`→`shemYechida`. Description still from list metadata (no full-description fetch yet). |

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
- **Source filter** — multi-select panel (see §4a). No longer a `<select>` element.
- **Employer-type map** — assigns each source to `private` / `public` / `academic` /
  `nonprofit` (the 4 filter options). There is **no "Advisory" filter type** — "Advisory"
  is only a textual grouping in the info block. KPMG/Deloitte/EY are `private`.
- **`AGENCY_SOURCES`** = `{'gf','huji-alumni'}` — job boards/agencies excluded from the
  "real employer" counts.
- **Job pop-up** reads `r.description`; a norm function must pass `description` for the
  pop-up to show anything.

`LI_RAW = https://raw.githubusercontent.com/Genys30/jobfinder/main/`

### 4a. Multi-select filters

Six filters use a **custom checkbox-based dropdown** (`.ms-wrap` / `.ms-btn` / `.ms-panel`)
instead of a `<select>`: **Role, Level, Employer Type, Source, Type (worktype), Contract**.

- Filter state is stored in JavaScript `Set` objects: `selectedSegments`, `selectedLevels`,
  `selectedSectors`, `selectedSources`, `selectedWorktypes`, `selectedPositiontypes`.
- Empty Set = no filter on that dimension; selecting multiple values = OR logic within that filter.
- `readFilterCriteria()` returns these Sets in the `criteria` object passed to `jobPassesFilters()`.
- `js/filters.js` — updated to accept Sets: checks `set.size > 0` before filtering, uses `set.has(value)`.
- `js/url-state.js` — updated: multi-select keys serialized as comma-separated in URL
  (e.g. `?segment=rd,data&level=senior`); `MS_KEYS` list drives serialization/deserialization.
- `updateMsBtn(btn, set, defaultLabel)` — updates button label: default / single value name / "N selected".
- `initMsPanel(btn, panel, set, clearEl, defaultLabel)` — wires open/close, checkbox changes, clear.
- Saved searches (`SAVED_KEY = 'jf_saved_searches_v3'`) — store/restore Sets as arrays. Key bumped from v2 (format incompatible).
- Analytics chart clicks (Role, Level, Worktype donuts) — still work: set the relevant Set to a single value and call `applyFilters()`.
- `company`, `date`, `sort`, `entropy` remain plain `<select>` elements.

**Adding a new option to a multi-select filter:** add a `<li class="ms-item" data-value="...">` row to the relevant `*Panel` list in `index.html`. No JS changes needed.

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
- **Remove** from: data bar status row, source filter panel items, status-map list, and any
  `if(activeSrc==='{x}')` branch. `load{X}` keeps only the array-fill (no status writes).
- **Add** `'{x}':'private'` (or correct type) to the employer-type map.
- Make sure `norm{X}` passes `description` so the job pop-up works.

---

## 8. `run_fetch.bat` — the local nightly runner (35 steps)

1. git pull (with `git reset --hard` + LinkedIn CSV backup/restore + `clean_linkedin_csv.py`)
2. Telegram @biltiformali · 3. Rambam · 4. BGU · 5. Maccabi · 6. MOD
7. Clalit · 8. TAU · 9. Haifa · 10. Bar-Ilan · **11. Afeka** · **12. SCE (PW)** · **13. Braude** · **14. HIT (cffi)** · **15. Azrieli (cffi)** · **16. Shenkar** · **17. Sapir (CIVI)** · **18. Emek Yezreel (YVC)** · **19. Tel-Hai** · **20. Ruppin (PW)**
21. Ichilov · 22. GotFriends · 23. HUJI positions
24. Shaare Zedek (PW) · 25. Hadassah (PW)
26. Deloitte (PW) · 27. EY (PW) · 28. BIS (PW) · 29. Joint (PW)
30. Osem-Nestlé (curl_cffi) · 31. Teva Pharmaceuticals (req) · **32. NAMER (req, APIM)**
33. `check_health.py` (health report) · 34. rclone upload all CSVs → Google Drive
35. commit + push (`git add -- *.csv health_report.json`, then `git pull --rebase` + push)

**Note:** `fetch_jobs.py` (ATS sources — Comeet incl. KPMG, Greenhouse, Lever, Ashby) and
`fetch_gotfriends.py` are **not** steps in the bat — they run automatically in the nightly
**GitHub Actions** CI (see §2), so they're not re-run locally.

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
- **Every new `norm{Source}` MUST pass `positionType: g('position_type')`.** If omitted, the
  frontend reads `undefined` and silently defaults the job to **full-time** — so maternity-cover
  / part-time jobs show the wrong badge and the Contract filter misses them. (Hit bar/afeka/sce/
  braude/bis at once on 2026-06-22.) Scrapers must also emit only the values the Contract filter
  knows: `full_time` (or '') / `maternity_cover` / `part_time` / `freelance` / `internship` —
  any other value (e.g. `postdoc`, `temporary`, `external_lecturer`) renders a blank badge and
  isn't filterable, so map those to '' (full-time) instead.
- A scraper tested with a single-company call (e.g. `run_comeet([{...}], {})`) will
  **overwrite that source's CSV with only that company** — don't commit such a partial CSV;
  the full nightly run regenerates it.
- **Keep this doc current.** At the end of every session, update `ARCHITECTURE.md` — add a
  Session-log entry (§11) and revise any section the session changed. Claude proposes this
  update by default at session end (same as it does for `BACKLOG.md`).
- **Import checkpoint must order by DATE, not filename (fixed 2026-06-15).** `processBatch`
  used to compare files by full name (`f.name > checkpoint`). Filenames start with the source,
  so `workable_jobs_…06-15` sorted AFTER `bgu_jobs_…06-16` (`w` > `b`) and silently blocked
  every later import — `Raw` froze at 2026-06-04 while Drive had files through the 15th.
  Fix: order/compare by `fileKey(name)` = `"YYYY-MM-DD|filename"` (date first, name as
  tiebreaker). File-level resume precision is preserved. `processBatch` self-heals a legacy
  name-based checkpoint on first run; `migrateCheckpointFormat()` does it manually.
- **Developer tooling — `rtk` (token compression):** A Rust CLI tool that compresses shell
  command output before passing it to LLMs (60–90% token reduction). Installed as a native
  Windows binary (`rtk.exe`) at `~/bin/rtk.exe` (Git Bash PATH). `~/.claude/settings.json`
  created with PreToolUse hook. Anna uses Claude.ai (browser), not Claude Code — hook is not
  active yet. Node.js not installed; Claude Code setup pending. Manual usage in Git Bash:
  `rtk git status`, `rtk git diff`, `python script.py 2>&1 | rtk pipe`.
  This is a developer tooling note only — `rtk` is not part of JobFinder's data pipeline.

---

## 11. Session log

Newest first. Keep entries short — details go in `BACKLOG.md`.

### 2026-06-29 — `.gitignore` hygiene (probe/recon/wire ignores; stray duplicate removed)
- Appended a **recon/probe/wire ignore block** so per-session one-off scripts and recon dumps
  never get committed: `probe_*.py`, `*_probe*.py`, `*_recon.py`, `wire_*.py`, `diag_*.py`, plus
  output backups `*.namerbak`, `*_live.html`, `*_live.bat`, `namer_probe_out/`. Verified the globs
  catch the probe/wire clutter but **not** production files (`fetch_*.py`, `index.html`,
  `run_fetch.bat` — `*_live.bat` ≠ `run_fetch.bat`, `*_live.html` ≠ `index.html`).
- Removed a stray tracked **`gitignore`** (no leading dot) — a duplicate-typo of `.gitignore`
  that had been committed by mistake.
- Commit `0f4adc9` (2 files, +13/−27). **Reminder:** the first attempt at this fix was wiped
  earlier by `run_fetch.bat`'s opening `git reset --hard HEAD` — commit `.gitignore`/doc edits
  **before** running the bat.

### 2026-06-28 — NAMER added (municipalities expansion, track A — national local-authority feed)
- **New source `namer`** (employer-type **`public`**) — the Ministry of Interior's national
  system for local-authority personnel tenders (מכרזי כוח אדם, רשויות מקומיות / עיריות /
  מועצות), `fetch_namer.py` → `namer_jobs_*.csv`. **One feed → hundreds of authorities**
  (~580 open on first run, incl. חיפה, פתח תקווה). First step of the municipalities plan
  (recon picked "one shared portal" over per-city scrapers).
- **API (recon, 6 probe rounds):** the site (`namerz.moin.gov.il/namer`) is an Angular SPA
  backed by an Azure **APIM gateway** — `https://ministryofinteriorapim.azure-api.net/
  namer-anonymous/v1/api/ManageMichrazim/GetAllSiteMichrazim/?basePage=<json>`, **anonymous**
  with a public `Ocp-Apim-Subscription-Key` (product `namer-anonymous`). Same-origin `/api`
  is just the SPA shell — the real API is the APIM host.
- **`basePage` gotcha (the long pole):** the list call takes a single query param `basePage` =
  JSON of a filter object. Filters MUST be **`null`, not `[]`** (empty arrays NRE the server);
  `page:{Number,SumItem}` is required (missing it → Int32 error). Full shape:
  `{page:{Number,SumItem},search:{attName:""},sort:[{attName:"SgiratMichrazDate",desc:false}],
  statusimFilter:null,…,rashuyotFilter:null,showAllMichrazimInRashut:false}`. Pagination by
  `page.Number` (0-based), stop on empty page. The exact shape + the key were captured from the
  live request via a Playwright network-capture probe after JSON-guessing failed.
- **Scraper:** key re-derived from the JS bundle at runtime (32-hex regex) with a hardcoded
  fallback; real publish date (`ptichatMichrazDate`) → **no first_seen**; per-job url
  `namerz.moin.gov.il/showexternal/{misparAsmachta}/{oid}` (the `/michraz/` guess was wrong;
  the blob SAS link is the time-limited PDF, not used); **dedup by `misparAsmachta`** (oid is
  not unique alone); open only (`kodStatus=0`/`פתוח`, skip cancelled/postponed). v1 no detail
  fetch → description from list metadata (תפקיד/רשות/מחוז/תחום/דירוג/השכלה/dates).
- **Title fix (variant C, same day):** `shemTafkid` is "אחר" in **164/597** rows (useless as a
  title). `fetch_detail_title` pulls **`teurMichraz`** (the real role name, absent from the list)
  from the detail endpoint **`Michraz/GetSiteMichraz/{asmachta}/{oid}`** — the working path was
  found by capturing the live request (`ManageMichrazim/…` and `Michrazim/…` both 404; it's
  singular **"Michraz"**, GET, asmachta+oid in path). Throttled 0.3s + cached, fired only for
  'אחר'/blank rows; B-fallback (`tchumMiktzoi`→`shemYechida`) on any failure so it never reverts
  to "אחר"; `_clean_teur` drops a trailing "הארכה". Prod: **164/164** got `teurMichraz`.
- **Frontend (`index.html`):** `normNamer`/`loadNamer` (Tel-Hai template — dedup by url, +
  `positionType`), data-bar pill, source filter, `DATABAR_SOURCES`, `'namer':'public'`, `--nm`
  colour (#0f766e), all 4 pools + `activeSrc`. **`run_fetch.bat`:** NAMER inserted as **step
  32/35** (req, last fetch step before health check); health/drive/commit → 33/34/35.
- **Backlog:** ~~`title=אחר` fallback~~ → **done same day (variant C, detail `teurMichraz`)**;
  full descriptions via `Michraz/GetSiteMichraz/{asmachta}/{oid}` (endpoint now wired);
  try moving NAMER to CI (APIM is Azure, not a gov server — datacenter IP may pass); **track B**
  = Hunter-platform cities (Tel-Aviv confirmed on `telaviv-int.hunterhrms.com`).

### 2026-06-25 — Ruppin College added (general-colleges expansion, source #4 of 4 — branch COMPLETE)
- **New source `ruppin`** (employer-type `academic`) — Ruppin Academic Center's **own** open
  positions (`fetch_ruppin.py` → `ruppin_jobs_*.csv`), Emek Hefer. 17 jobs (9 academic + 8 admin,
  1 maternity_cover). The **4th & final** general college — general-colleges branch now COMPLETE.
- **Imperva WAF (status 247)** — plain requests AND curl_cffi both blocked → **non-headless
  Playwright** (`headless=False` + `--disable-blink-features=AutomationControlled`). LOCAL-ONLY
  (cannot run in CI). `fetch_ruppin.py` built on the proven recon selectors (`div.card` →
  `.card-header`/`.card-body`).
- **Two pages, department by page** (Tel-Hai pattern): `/administration/academic-staff-required/`
  → academic_faculty, `/administration/administrative-staff-required/` → admin_staff.
- **Mixed apply shapes** (key design point): academic = apply by **email**, no per-job URL →
  `url` = page URL, inline description from the card body; admin = per-job **PDF** (מכרז) link →
  `url` = PDF, description empty. Frontend dedups **uniformly by title+url** (admin urls differ;
  academic share the page url but titles differ — so title+url is safe for both, no mixed-key code).
- **`clean_title` gotcha:** academic titles carried zero-width + bidi marks; since academic is
  **title-keyed**, those are stripped so a drifting invisible char can't make a job look "new"
  each run. `position_type` = `maternity_cover` if title has חל"ד, else '' (only whitelisted
  values). External-only filter (`פנימית` skipped) — 0 internal now, stub for future.
- **Frontend (`index.html`):** `normRuppin`/`loadRuppin` (YVC template — dedup title+url,
  + `positionType`), data-bar pill, source filter, `DATABAR_SOURCES`/status-map, `'ruppin':'academic'`,
  `--rp` colour (#7b4fa0), all 4 pools + `activeSrc`. **`run_fetch.bat`:** Ruppin inserted as
  **step 20/34** (PW non-headless, after Tel-Hai); later steps renumbered.
- **General-colleges branch COMPLETE (4/4):** Sapir (CIVI) · Emek Yezreel/YVC (req) · Tel-Hai
  (Drupal/req) · Ruppin (PW). With the engineering branch (6/6), **all 10 colleges are now sources.**

### 2026-06-24 — Tel-Hai College added (general-colleges expansion, source #3 of 4)
- **New source `telhai`** (employer-type `academic`) — Tel-Hai Academic College's **own** open
  positions (`fetch_telhai.py` → `telhai_jobs_*.csv`), Galilee. ~27 jobs (7 academic + 20 admin).
  **Drupal** (Olivero theme, Views), server-rendered, **no WAF** → req+BS4. (`web_fetch` is
  bot-blocked on this site, but plain `requests` works fine from an Israeli IP — recon was done
  via a probe script run by Anna rather than direct fetch.)
- **Two separate pages, department by page** (cleaner than keyword-guessing): `/jobs` →
  academic_faculty, `/jobs-2` → admin_staff. Each renders a Views **table** — `tr` →
  `td.views-field-title a[href^="/position/"]` (real per-job URL) plus metadata cells: job
  code, scope (`field-job-scope`), availability, **exteral-internal** [sic — site's own typo]
  flag, submission deadline.
- **External-only filter (Anna's explicit choice):** rows flagged פנימית (internal) are
  skipped during scrape — internal-only postings aren't useful in a public job feed. `0`
  internal rows were present on this run, but the filter stays in for future runs.
  `position_type` is derived from the scope cell (חצי משרה → part_time, חל"ד → maternity_cover).
- Real per-job `/position/NNNN` URLs → `first_seen`/dedup by **url** (SCE/Sapir pattern). Several
  jobs share an identical title ("קול קורא לגיוס חבר/ת סגל...") across different faculty
  clusters — each has a distinct `/position/` id, so they correctly stay separate. v1 does
  **not** fetch the `/position/` detail pages (would add 25-30 requests/night) — `description`
  is built from the row's own metadata cells instead.
- **Frontend (`index.html`):** `normTelhai`/`loadTelhai` (SCE/Sapir template — dedup by **url**
  — + `positionType`), data-bar pill, source filter, `DATABAR_SOURCES`, `'telhai':'academic'`,
  `--th` colour, all 4 pools + `activeSrc`. **`run_fetch.bat`:** Tel-Hai inserted as **step
  19/33** (req, after Emek Yezreel).
- **General-colleges branch: 3/4 done** (Sapir, YVC, Tel-Hai). Only **Ruppin** remains — behind
  Imperva (status 247), needs Playwright; separate go/no-go given its low relevance (mostly
  maintenance/secretary/marketing postings).

### 2026-06-24 — Emek Yezreel / YVC College added (general-colleges expansion, source #2 of 4)
- **New source `yvc`** (employer-type `academic`) — Max Stern Yezreel Valley College's **own**
  open positions (`fetch_yvc.py` → `yvc_jobs_*.csv`), Yezreel Valley. ~5 jobs, all academic
  course positions (page currently lists only faculty/course roles). WordPress (theme `emek`),
  **no WAF** → req+BS4.
- **Name-collision caught (like `--sp`):** `EMEK_JOBS` already exists for **HaEmek Medical
  Center** (Afula hospital) → the college uses source key **`yvc`** (domain/abbreviation),
  var `YVC_JOBS`, colour `--yvc`, label "Emek Yezreel". Always grep the live file for the
  candidate key/var/colour before wiring a new source.
- **Structure:** single accordion `section.q-and-a` → `div.question-item` → `a.question-link
  span` (toggle) + `div.answer` (body). **Duplicate-title gotcha (like HIT):** the toggle text
  repeats (two "…מחפש מרצה לקורס" for nursing, two for educational counseling); the course name
  lives in the body's first `<p>` → the title is **enriched with the course** ("…לקורס: עקרונות
  השיקום") to make it unique. `#questionN` is sequential/unstable → not used as a key; first_seen/
  dedup by the enriched **title**. Descriptions inline (course summary/schedule/requirements).
- **Frontend (`index.html`):** `normYVC`/`loadYVC` (Braude template, dedup `title+url`), pill,
  source filter, `DATABAR_SOURCES`, `'yvc':'academic'`, `--yvc` colour, all 4 pools + `activeSrc`
  (verified `EMEK_JOBS` hospital untouched). **`run_fetch.bat`:** YVC inserted as **step 18/32**.
- **General-colleges branch: 2/4 done** (Sapir, YVC). Next: Tel-Hai → Ruppin (Imperva/PW, last).

### 2026-06-24 — Sapir College added (general-colleges expansion, source #1 of 4)
- **New source `sapir`** (employer-type `academic`) — Sapir Academic College's **own** open
  positions (`fetch_sapir.py` → `sapir_jobs_*.csv`), Sderot. First **general** (non-engineering)
  college. ~21 jobs (scope = academic **+ admin**, Anna's choice). `'sapir':'academic'` in the
  employer-type map (it's an academic institution).
- **CIVI ATS feed:** `sapir.ac.il/hr/wanted` redirects to `app.civi.co.il/promos/id=NLY65YEJTW
  &src=13586`, scraped directly (req → curl_cffi fallback). Each job = `div.thumb-content` →
  `.title` + `.descr` (inline rich → pop-up works). Job id from the `openPromo(event,<ID>,13586,1)`
  onclick → per-job URL `app.civi.co.il/promo/id=<ID>&src=13586` (real per-job URL → dedup by
  **url**, SCE pattern).
- **Pagination (key lesson):** CIVI ignores `?rows=N` but honours **`&p=N`** (20 jobs/page).
  Probed by counting distinct `openPromo` ids per param: only `p=2` returned new ids. Scraper
  loops `&p=1,2,…` until a page yields no new cards. (Got 20 on p1 + remainder on p2.)
- `department` inferred from title keywords (חבר סגל/מרצה/מנחה/רקטור/דיקן → academic, else admin),
  since the CIVI feed has no academic/admin section split. Mostly admin (general college).
- **Frontend (`index.html`):** `normSapir`/`loadSapir` (SCE template — dedup by **url** —
  + `positionType`), data-bar pill, source filter, `DATABAR_SOURCES`, `'sapir':'academic'`,
  all 4 pools + `activeSrc`. **Colour-var collision caught:** `--sp` was already taken by the
  existing **Direct** source → Sapir uses **`--spr`** instead (verified Direct's pill/badges
  intact). **`run_fetch.bat`:** Sapir inserted as **step 17/31** (CIVI, after Shenkar).
- **General-colleges branch: 1/4 done** (Sapir). Next: Emek Yezreel → Tel-Hai → Ruppin (Imperva/PW, last).

### 2026-06-23 — Shenkar College added (engineering-colleges expansion, source #6 — branch complete 6/6)
- **New source `shenkar`** (employer-type `academic`) — Shenkar College of Engineering &
  Design's **own** open positions (`fetch_shenkar.py` → `shenkar_jobs_*.csv`), Ramat Gan.
  6 jobs (all academic faculty). WordPress (WPML), **no WAF** → req+BS4.
- **Different structure (key lesson):** unlike the 5 accordion colleges, Shenkar's page is a
  flat list of **links to external Google Docs/Drive** documents — no inline job text on the
  page. Job links are identified by href (`docs.google.com`/`drive.google.com`) + a title
  marker. **No descriptions** (v1 leaves `description` empty — the body is in the external doc;
  pop-up is blank, accepted). The links ARE real per-job URLs → `first_seen`/dedup by **url**.
- `clean_title` strips a trailing posting-date `(10.04.2025)` and fixes the site's slash-wrap
  "דרוש/ ה" → "דרוש/ה". Small list (~6), includes some older postings still on the page.
- **Frontend (`index.html`):** `normShenkar`/`loadShenkar` (SCE template — dedup by **url** —
  + `positionType`), data-bar pill, source filter, `DATABAR_SOURCES`, `'shenkar':'academic'`,
  `--sh` colour, all 4 pools + `activeSrc`. **`run_fetch.bat`:** the live bat was missing the
  **Azrieli** step (its bat update wasn't pushed) → this session inserted **both** Azrieli
  (step 15, cffi) and Shenkar (step 16, req) → **30 steps**.
- **Engineering/tech-colleges branch COMPLETE (6/6):** Afeka (req) · SCE (PW) · Braude (req) ·
  HIT (cffi) · Azrieli (cffi) · Shenkar (req). All six engineering/technology colleges' own
  positions are now sources. Next academic tier (if pursued): general colleges with eng/CS
  faculties (Ruppin, Tel-Hai, Emek Yezreel, Sapir) — lower relevance density, separate decision.

### 2026-06-22 — Azrieli College added (engineering-colleges expansion, source #5 — branch complete 5/5)
- **New source `azrieli`** (employer-type `academic`) — Azrieli College of Engineering
  Jerusalem (JCE)'s **own** open positions (`fetch_azrieli.py` → `azrieli_jobs_*.csv`),
  Jerusalem. 10 jobs (5 academic + 5 admin). WordPress (theme `roots-mipo`), server-rendered.
- **WAF 403** on plain requests (~5 KB block page) → **curl_cffi** `chrome110` (200, ~182 KB),
  same as HIT/Osem (warm-up on home + retries). No redirect-loop like HIT — a direct 403.
- **Two-section custom accordion:** `div#academic-staff` (academic) / `div#administrative-staff`
  (admin); each job `div.unit` → `div.unit_name > h3` (title) + `div.unit_content` (description,
  inline & rich → pop-up works). `department` by section id (HIT pattern). No per-job URL
  (apply by email) → `first_seen` by **title**, frontend dedup `title+url` (Braude pattern).
  Worked first try (10 jobs, descriptions 171–1000 chars, no dups).
- **Frontend (`index.html`):** `normAzrieli`/`loadAzrieli` (Braude template + `positionType`),
  data-bar pill, source filter item, `DATABAR_SOURCES`, `'azrieli':'academic'`, `--az` colour,
  all 4 pools + `activeSrc`. **`run_fetch.bat`:** Azrieli inserted as **step 15/29** (cffi,
  after HIT); later steps renumbered.
- **Engineering-colleges branch COMPLETE (5/5):** Afeka (req) · SCE (PW) · Braude (req) ·
  HIT (cffi) · Azrieli (cffi). Five own-positions academic sources added end-to-end this run.

### 2026-06-22 — HIT College added (engineering-colleges expansion, source #4)
- **New source `hit`** (employer-type `academic`) — HIT / Holon Institute of Technology's
  **own** open positions (`fetch_hit.py` → `hit_jobs_*.csv`), Holon. 15 jobs (2 admin +
  13 academic). WordPress, server-rendered, **but behind a Sucuri/SPD gateway**: plain
  requests 302-loop to `//abuse.spd.co.il` (sets ZNPCQ/HITHTTPSSRVID cookies) → **curl_cffi**
  `chrome110` (like Osem). `fetch_html()` warms up on the home page (lets the gateway set
  cookies on the session), then fetches `/jobs/` with retries (timeout/5xx).
- **Two-tab Bootstrap accordion:** `div#JOB_accordion0` (admin) / `div#JOB_accordion1`
  (academic); each job `div.accordion-item` → `div.accordion_title` + `div.accordion-body`
  (inline & rich → pop-up works). `department` by tab id.
- **Duplicate-title gotcha (key lesson):** two distinct postdocs both titled "משרת פוסטדוק |
  Postdoctoral Position" (different labs) — a title-only or page-URL-only key collapsed one
  (14 instead of 15). Fix: each accordion item carries a unique `#collapseN` id
  (`data-bs-target`/`.accordion-collapse[id]`, post-id based, stable). Appended to the page
  URL as a fragment → unique per-job url; `first_seen`/dedup by **url**; frontend dedup
  `title+url`. Side effect (accepted): the `#collapseN` link lands on the page (HIT doesn't
  auto-open the accordion/tab by hash) — same UX as Afeka/Braude, but data is complete.
- **internship false-match fixed:** the broad `intern(ship)?` regex matched "INTERNational"
  / "internal" in descriptions (4 fake internships) → word-boundary `\bintern\b` + dropped the
  broad Hebrew "התמחות". position_type only emits frontend-known values
  (maternity_cover/part_time/freelance/internship; postdoc/visiting → '' = full_time).
- **Frontend (`index.html`):** `normHIT`/`loadHIT` (Braude template, dedup `title+url`),
  data-bar pill, source filter item, `DATABAR_SOURCES`, `'hit':'academic'`, `--hit` colour,
  all 4 pools + `activeSrc`. **`run_fetch.bat`:** HIT inserted as **step 14/28** (cffi, after
  Braude); later steps renumbered.

### 2026-06-21 — Braude College added (engineering-colleges expansion, source #3)
- **New source `braude`** (employer-type `academic`) — ORT Braude College of Engineering's
  **own** open positions (`fetch_braude.py` → `braude_jobs_*.csv`), Karmiel. 17 jobs
  (9 admin + 8 academic). WordPress, server-rendered, **no WAF** → req+BeautifulSoup (the
  easiest of the three colleges). Foundation accordion: `li.accordion-item` →
  `a.accordion-title` (title) + `div.accordion-content` (description).
- **Descriptions are inline & rich** (unlike SCE) → the job pop-up works. One page, two
  sections (משרות מנהליות / משרות אקדמיות); `department` is set by the nearest preceding
  section heading via `li.find_previous(SECTION_RX)`, with a title-keyword fallback
  (מרצה/חבר סגל/מתרגל → academic). Job-marker filter guards any non-job accordions.
- **No per-job URL** (titles link to `#`, apply by email) → `first_seen` keyed by **title**
  (Afeka/BGU pattern); url = page URL; frontend dedup by `title+url`. Worked first try.
- **Frontend (`index.html`):** `normBraude`/`loadBraude` (Afeka template, dedup `title+url`),
  data-bar pill, source filter item, `DATABAR_SOURCES`, `'braude':'academic'`, `--bd` colour,
  all 4 pools + `activeSrc`.
- **`run_fetch.bat` fix:** the live bat was still missing the **SCE** step (its bat update was
  never deployed — only SCE's scraper + frontend went out). This session inserted **both**
  SCE (step 12, PW) and Braude (step 13, req) after Afeka → **27 steps**.

### 2026-06-21 — SCE College added (engineering-colleges expansion, source #2)
- **New source `sce`** (employer-type `academic`) — SCE / Sami Shamoon College of Engineering's
  **own** open positions (`fetch_sce.py` → `sce_jobs_*.csv`). 20 jobs (9 admin + 8 academic +
  3 research) across the three HR "wanted" sub-pages (admin / academic / post-doc-researches).
- **WAF JS-challenge** — plain requests AND curl_cffi `chrome110` both returned 403 (the
  challenge cookie is JS-set). Escalated to **Playwright**: one shared browser context warms up
  on the hub (`/wanted`), the challenge clears once, then the 3 sub-pages reuse the cookie. The
  HTML itself is server-rendered (no clicking/JS-render needed) — Playwright is only there to
  pass the challenge. Uses `sync_playwright().start()/.stop()` (not `with`) to avoid re-indenting.
- **Mixed link shapes** (key lesson): admin jobs link to the external **CIVI** ATS
  (`app.civi.co.il/promo/id=N&src=M`); academic/research link to **internal** SCE detail pages
  (`/wanted/{section}/{slug}`). The job-link selector matches CIVI promo links OR any child of
  the current sub-page path. The initial CIVI-only selector silently missed all 11 academic +
  research jobs (they showed as 0).
- **URL gotchas:** (1) the CIVI `&src=` param is **required** — stripping it 404s, so the full
  CIVI URL is kept (only `#fragment` dropped); (2) the site emits doubled-domain internal hrefs
  (`/www.sce.ac.il/...`) → `normalize_url` strips a redundant leading domain and rebuilds.
  Real per-job URLs → `first_seen`/dedup by **url** (unlike Afeka's title key).
- **Title cleanup:** link labels are doubled and sometimes carry a `| sitename` suffix
  (title-attr vs visible text) → `clean_title` drops the `|` suffix, then collapses the smallest
  repeated word-prefix. v1: **no descriptions** (admin = CIVI detail page, academic = internal
  detail page; both un-fetched, like Deloitte).
- **Frontend (`index.html`):** `normSCE`/`loadSCE` (Afeka/BAR template, dedup by url), data-bar
  pill, source filter item, `DATABAR_SOURCES` entry, `'sce':'academic'`, `--sce` colour, added
  to all 4 job pools + `activeSrc`. **`run_fetch.bat`:** SCE inserted as **step 12/27** (PW,
  after Afeka); later steps renumbered.

### 2026-06-21 — Afeka College added (engineering-colleges expansion, source #1)
- **New source `afeka`** (employer-type `academic`) — Afeka Tel Aviv Academic College of
  Engineering's **own** open positions (`fetch_afeka.py` → `afeka_jobs_*.csv`). Scrapes the
  college's "Working at Afeka" page (`/about-afeka/general-information/jobs/`), **not** the
  Afeka Jobs student/alumni portal. Umbraco CMS, server-rendered Bootstrap accordion →
  req+BeautifulSoup (no Playwright). 11 jobs (9 admin staff + 2 academic faculty).
- **Patterns:** `first_seen` keyed by **title** (all jobs share one page URL, like BGU);
  job-marker filter (`תיאור התפקיד`/`דרישות`/`להגשת קורות חיים`/Requirements/Send CV) drops the
  events accordion; `detect_department` classifies admin vs academic **by title only**
  (description mentions "סגל אקדמי" in context and would mis-flag a lab technician); 0-row guard.
- **Frontend (`index.html`):** `normAfeka`/`loadAfeka` (BAR template), data-bar pill, source
  filter item, `DATABAR_SOURCES` entry, `'afeka':'academic'`, `--af` colour, added to all 4
  job pools + `activeSrc` branch. **Dedup by `title+url`** (not `url`) — the 2 academic jobs
  share the page URL, so url-only dedup would collapse one.
- **`run_fetch.bat`:** Afeka inserted as **step 11/25** (local-only, after Bar-Ilan); all
  later steps renumbered. ATS apply links (`campaign.adamtotal.co.il`) become each admin job's
  `url`; academic jobs (email-only) fall back to the page URL.
- **Template-first:** Afeka is the proven template for the remaining engineering colleges
  (SCE, Braude, HIT, Azrieli) — see `BACKLOG.md`.

### 2026-06-16 — LinkedIn weekly post (template + auto-draft)
- **`linkedin_weekly_template.md`** — reusable bilingual (HE+EN) weekly post template with
  `{{…}}` placeholders, a filled example, a fill guide (which TitleTrends cell feeds which
  field), and editorial rules. Insights-focused, lively tone. (Lives in outputs, not the repo.)
- **`buildLinkedInPost()`** added — auto-drafts the post from WEEKLY TitleTrends into a
  `LinkedInPost` sheet. Companies named only for RISING/NEW; DECLINING role-only. New cosmetic
  helpers `cleanTitleForPost_` / `dominantCompany_` (post display only — do not change Raw or
  the TitleTrends grouping). See §12.
- Confirmed first TitleTrends day-over-day run on fresh data (to 2026-06-16) after the import
  checkpoint fix — weekly window non-empty, monthly no longer under-counted.

### 2026-06-15 — TitleTrends + import checkpoint fix
- **`analyzeTitleTrends()`** added (new **TitleTrends** sheet): rising / declining / new /
  removed job **titles**, WEEKLY (7v7) + MONTHLY (30v30), four tables each + a `companies`
  column (top-10 employers per title). Flow model by first-seen `date`; aggregators
  (gotfriends, huji_alumni) and recruiter/garbage rows excluded; coverage guard requires a
  source in BOTH windows (≥5 weekly / ≥20 monthly). Weekly trigger Sun 08:00
  (`setupTitleTrendsTrigger`). Reuses RoleTrends helpers. See §12.
- **🔴 Import checkpoint bug fixed** — `processBatch` compared files by name, so
  `workable_jobs_*` (last alphabetically) froze the checkpoint and blocked all earlier-named
  files on later dates; `Raw` had stalled at 2026-06-04. Now orders by `fileKey` =
  `date|name`; self-heal + `migrateCheckpointFormat()` migrate the old checkpoint. `Raw`
  rebuilt via `hardResetRaw()` → repeated `continueImport()` (46,778 rows through 2026-06-15).
- **Diagnostics added** to `Code.gs`: `debugDates` fix usage, `diagDateColumn`,
  `diagCheckpoint`, `hardResetRaw` (one-off `Raw` clear that avoids the
  "can't delete all non-frozen rows" error).
- Note: `Raw` stores `date` as Date objects (not strings); `parseDateSafe` handles both.

### 2026-06-07 (rtk developer tooling)
- **`rtk` token-compression tool** installed and documented (§10). `rtk.exe` at `~/bin/rtk.exe`
  (Git Bash PATH). `~/.claude/settings.json` created with PreToolUse hook. Anna currently uses
  Claude.ai (browser) — hook not active yet; Claude Code setup pending (Node.js not installed).
  Manual usage: `rtk git status`, `rtk git diff`, `python script.py 2>&1 | rtk pipe`.
  Developer tooling note only — `rtk` is not part of JobFinder's data pipeline.

### 2026-06-07 (session 2 — multi-select filters)
- **Multi-select filters** implemented in frontend (`index.html`, `js/filters.js`, `js/url-state.js`).
  Six filters converted from `<select>` to custom checkbox-panel dropdowns (`.ms-wrap` pattern):
  Role, Level, Employer Type, Source, Type (worktype), Contract.
- Filter state now stored in `Set` objects (`selectedSegments`, `selectedLevels`, etc.).
  Multiple selections = OR logic within a filter dimension.
- `js/filters.js` updated: `jobPassesFilters()` accepts Sets, uses `set.has()`.
- `js/url-state.js` updated: new `MS_KEYS` list, comma-separated URL params, `setMs`/`getMs` hooks.
- Saved searches key bumped to `v3` (old v2 saves incompatible — cleared on next visit).
- Analytics chart click-through (Role/Level/Worktype donuts) adapted to write Sets directly.
- See §4a for full architectural description.

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
| RoleTrends | Emerging/declining keywords + brand-new titles (`analyzeRoleTrends`, 20-category level) |
| TitleTrends | Rising/declining/new/removed job **titles**, weekly + monthly (`analyzeTitleTrends`) |

**Key functions:**
- `importIncremental()` — daily delta import (new files only)
- `resetAndImport()` / `continueImport()` — full reload from scratch
- `reclassifyRaw()` / `continueReclassify()` — re-run title classification on all Raw rows
- `buildCharts()`, `buildWeekly()` — rebuild individual sheets manually
- `debugOther()` — show top titles in "Other" category (helps improve classifier)
- `buildLinkedInPost()` — auto-drafts a bilingual (HE+EN) weekly LinkedIn insights post from TitleTrends into a `LinkedInPost` sheet (see below)

**Title classification (`classifyTitle` + `DEPT_MAP`):**
Maps job title → one of 20+ standard categories using keyword matching (EN + HE) and
exact-match lookup table. Applied at parse time and via `reclassifyRaw()`.

**Company filtering (`shouldExcludeCompany`):**
Companies sheet excludes: explicit recruiter blacklist (`RECRUITING_COMPANIES`), logo/image
filenames, names that look like job titles (2+ keywords like "engineer"/"developer"),
names containing recruiting keywords (השמה, staffing, headhunt…), names outside 2–80 chars.
To add a new recruiter: `"Company Name": true` in `RECRUITING_COMPANIES` in Code.gs.

**Title & role trend analysis (`analyzeRoleTrends`, `analyzeTitleTrends`):**
Two complementary trend tools, both reading `Raw`:
- `analyzeRoleTrends()` → **RoleTrends** sheet — keyword/category-level (emerging vs declining
  share, brand-new titles). v4: source-aware (sources need 30+ postings in both periods),
  Hebrew gender-suffix normalization.
- `analyzeTitleTrends()` → **TitleTrends** sheet — concrete job **titles**, two blocks
  (WEEKLY 7d-vs-7d, MONTHLY 30d-vs-30d), four tables each: RISING / DECLINING / NEW / REMOVED,
  plus a `companies` column (top-10 employers per title). **Flow model by first-seen date**:
  counts are NEW postings whose first-seen `date` falls in each window, so "REMOVED" means
  "no new postings this window", not "gone from the live site". Aggregators (`gotfriends`,
  `huji_alumni`) and recruiter/garbage rows excluded; only sources present in BOTH windows
  (≥5 weekly / ≥20 monthly) take part, so a newly-added or dropped scraper can't fake
  NEW/REMOVED. Weekly trigger: Sunday 08:00 via `setupTitleTrendsTrigger()`. Reuses
  `normalizeTitleForTrends_`, `shouldExcludeCompany`, `isGarbageRow_`, `parseDateSafe`.

**⚠ Freshness gate:** `analyzeTitleTrends`, `Weekly` and `Dashboard` are only meaningful when
`Raw` is current. `Raw` is fed from the **Drive archive** (not the repo) by `importIncremental`,
so if Drive uploads or the import lag behind, the recent window goes empty/under-counted.
Check `Max date seen in Raw` (e.g. via `debugDates`) before trusting recent trends.

**LinkedIn weekly post (`buildLinkedInPost`):**
Auto-fills a bilingual (Hebrew + English) market-insights post from the WEEKLY TitleTrends
data and writes it to a `LinkedInPost` sheet (Hebrew in A4, English in A6 — copy the cell).
Picks top-3 RISING (preferring titles confirmed in BOTH weekly and monthly), top-2 DECLINING,
top-2 NEW; falls back to monthly on a thin week. **Editorial rules:** companies are named only
for RISING/NEW (positive "who's hiring"); DECLINING is role-only (a drop is often one employer
winding down — don't name them). Cosmetic helpers `cleanTitleForPost_` (strips `- 236606`,
`(copy)`, emoji/ID tails — display only, does not touch Raw) and `dominantCompany_` (top employer
from the companies string). Run after `analyzeTitleTrends`. The reusable manual template +
fill guide lives in `linkedin_weekly_template.md` (outputs, not in repo).

**Important:** the site loads data from GitHub (not Drive). This dashboard is separate
from the live site — it reads the full Drive archive independently.
