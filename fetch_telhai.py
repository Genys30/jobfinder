#!/usr/bin/env python3
"""
fetch_telhai.py — Scrapes open positions at Tel-Hai Academic College
(המכללה האקדמית תל-חי / Tel-Hai) from the college's own "דרושים" pages.

  Academic: https://www.telhai.ac.il/jobs     → department = academic_faculty
  Admin:    https://www.telhai.ac.il/jobs-2    → department = admin_staff
  CMS: Drupal (Olivero theme, Views), server-rendered, NO WAF → requests + BS4.
  (web_fetch is bot-blocked, but plain requests works from an Israeli IP.)

  Each page is a Views TABLE; each job is a <tr> with cells:
    td.views-field-title           → <a href="/position/NNNN">TITLE</a>   (real per-job URL)
    td.views-field-field-job-code  → job code
    td.views-field-field-job-scope → scope (חצי משרה / משרה מלאה …) → position_type
    td.views-field-field-availability        → availability (מיידית …)
    td.views-field-field-exteral-internal    → חיצונית / פנימית  (external / internal)
    td.views-field-field-submission-deadline → deadline date

  We keep EXTERNAL jobs only (חיצונית); internal (פנימית) postings are for current
  staff and not useful in a public feed (Anna's choice).

  department is assigned by PAGE (cleaner than keyword guessing). Real per-job
  URLs → first_seen/dedup by url. v1 does NOT fetch the /position/ detail pages
  (would be 30-50 extra requests/night) — description is built from the row's
  metadata cells (scope · availability · deadline).

Output: telhai_jobs_YYYY-MM-DD.csv
Usage:  py fetch_telhai.py
"""

import csv, re, sys, glob
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"telhai_jobs_{TODAY}.csv"
SOURCE      = "telhai"
COMPANY     = "המכללה האקדמית תל-חי"
LOCATION    = "תל-חי"
BASE        = "https://www.telhai.ac.il"

PAGES = [
    ("https://www.telhai.ac.il/jobs",   "academic_faculty"),
    ("https://www.telhai.ac.il/jobs-2", "admin_staff"),
]

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

# external vs internal (keep only external)
INTERNAL_RX = re.compile(r'פנימי', re.UNICODE)

# scope → position_type
def scope_to_position_type(scope, title=''):
    text = (scope + ' ' + title)
    if re.search(r'חל"ד|חל״ד|החלפה לחופשת לידה|מילוי מקום', text):
        return 'maternity_cover'
    if re.search(r'חצי משרה|משרה חלקית|חלקית', text):
        return 'part_time'
    if re.search(r"סטאז'|מתמחה|\bintern", text, re.I):
        return 'internship'
    return ''   # full / unspecified → full_time


def clean(t):
    return re.sub(r'\s+', ' ', (t or '')).strip()


def load_first_seen():
    """Read the most recent previous telhai CSV → {url: date} dict.
    Real per-job /position/ URLs → key by URL."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("telhai_jobs_*.csv"))
    prev_file = None
    for f in reversed(candidates):
        if yesterday in f:
            prev_file = f
            break
    if prev_file is None and candidates:
        prev_file = candidates[-1]
    if prev_file is None:
        return {}
    result = {}
    try:
        with open(prev_file, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                u = row.get('url', '').strip()
                d = row.get('date', '').strip()
                if u and d:
                    result[u] = d
    except Exception:
        pass
    return result


def get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return None
    if not r.ok:
        print(f"  ✗ HTTP {r.status_code}")
        return None
    return r


def cell(tr, suffix):
    el = tr.select_one(f"td.views-field-{suffix}")
    return clean(el.get_text(" ", strip=True)) if el else ""


def scrape() -> list[dict]:
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    for url, dept in PAGES:
        print(f"\n[Tel-Hai] {url}  → {dept}")
        r = get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.select("tr")
        page_jobs = 0
        skipped_internal = 0
        for tr in rows:
            link = tr.select_one('td.views-field-title a[href^="/position/"]')
            if not link:
                continue
            title = clean(link.get_text(" ", strip=True))
            href = link.get("href", "")
            job_url = urljoin(BASE, href)
            if not title or not job_url:
                continue

            ext_int = cell(tr, "field-exteral-internal")  # site's spelling: "exteral"
            if INTERNAL_RX.search(ext_int):
                skipped_internal += 1
                continue

            scope    = cell(tr, "field-job-scope")
            avail    = cell(tr, "field-availability")
            deadline = cell(tr, "field-submission-deadline")

            if job_url in seen:
                continue
            seen.add(job_url)

            desc_parts = []
            if scope:    desc_parts.append(f"היקף: {scope}")
            if avail:    desc_parts.append(f"זמינות: {avail}")
            if ext_int:  desc_parts.append(ext_int)
            if deadline: desc_parts.append(f"מועד הגשה: {deadline}")
            desc = " · ".join(desc_parts)

            jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       LOCATION,
                "date":           first_seen.get(job_url, TODAY),
                "url":            job_url,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    desc[:1000],
                "position_type":  scope_to_position_type(scope, title),
            })
            page_jobs += 1

        print(f"  → {page_jobs} external jobs ({skipped_internal} internal skipped)")

    print(f"\n  → {len(jobs)} jobs total")
    return jobs


def main():
    jobs = scrape()

    # 0-row guard: skip CSV write so health check falls back to yesterday's file.
    if not jobs:
        print("\n⚠️  No jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\n✅ Wrote {len(jobs)} jobs → {OUTPUT_FILE}")
    print("\nSample:")
    for j in jobs[:15]:
        pt = f" [{j['position_type']}]" if j['position_type'] else ""
        print(f"  • [{j['department'][:6]}] {j['title'][:50]}{pt}")

    print("\nNext steps:")
    print("  git add -f telhai_jobs_*.csv")
    print("  git add fetch_telhai.py run_fetch.bat")
    print("  git commit -m 'feat: add Tel-Hai college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
