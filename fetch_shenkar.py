#!/usr/bin/env python3
"""
fetch_shenkar.py — Scrapes open positions at Shenkar College of Engineering &
Design (שנקר — הנדסה. עיצוב. אמנות, Ramat Gan) from the college's own
"דרושים/ות ברחבי שנקר" page.

  Source: https://www.shenkar.ac.il/he/pages/jobs-shenkar/
  CMS:    WordPress (WPML), server-rendered. No WAF — plain requests + BS4.

  STRUCTURE DIFFERS from the 5 engineering colleges: this page is NOT an
  accordion with inline jobs. It's a flat list of links, each pointing to an
  EXTERNAL document (Google Docs / Google Drive PDF) with the full job text:
      <a href="https://docs.google.com/...">קול קורא לתפקיד ...</a>
      <a href="https://drive.google.com/file/...">דרוש/ה מרצה ...</a>
  So job links are identified by their href (docs.google.com / drive.google.com)
  and there are NO inline descriptions (the body lives in the external doc; v1
  does not fetch/parse it). The links ARE real per-job URLs → first_seen/dedup
  by URL (like SCE).

  All postings on this page are academic faculty roles (מרצה / ראש מחלקה /
  מרצים) → department = academic_faculty. Admin jobs are not posted here.

This is the college's OWN open positions (employer-type: academic). Note the
list is small (~6) and may include older postings the college still lists.

Output: shenkar_jobs_YYYY-MM-DD.csv
Usage:  py fetch_shenkar.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"shenkar_jobs_{TODAY}.csv"
SOURCE      = "shenkar"
COMPANY     = "שנקר — הנדסה. עיצוב. אמנות"
LOCATION    = "רמת גן"
PAGE_URL    = "https://www.shenkar.ac.il/he/pages/jobs-shenkar/"

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

# A job link points to an external Google Docs / Drive document.
JOB_HREF_RX = re.compile(r'(docs\.google\.com|drive\.google\.com)', re.I)

# Title must look like a job posting (guards against any stray google links).
TITLE_MARKER_RX = re.compile(r'דרוש|דרושים|קול קורא|מרצה|מרצים|משרה|מועמד', re.UNICODE)

# ── position_type (only frontend-known values; else '' → full_time) ───────────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|'
        r'מילוי מקום לחופשת לידה|ממלא.?ת? מקום|maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|חצי משרה|part.?time',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|מתמחה|\bintern\b|\binternship\b|\btrainee\b",
        re.I | re.UNICODE
    ),
}

def detect_position_type(title=''):
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(title or ''):
            return pt
    return ''


def clean_title(t):
    """Normalize whitespace and drop a trailing posting-date in parens, e.g.
    'דרוש/ה מרצה ... (10.04.2025)' → 'דרוש/ה מרצה ...'."""
    t = re.sub(r'\s+', ' ', (t or '')).strip()
    # the site sometimes wraps after a slash, leaving "דרוש/ ה" / "מרצה/ ית"
    t = re.sub(r'/\s+', '/', t)
    t = re.sub(r'\s*\(\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*\)\s*$', '', t).strip()
    return t


def load_first_seen():
    """Read the most recent previous shenkar CSV → {url: date} dict.
    Job links are real per-job URLs (external docs) → key by URL."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("shenkar_jobs_*.csv"))
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
    if r.status_code == 403:
        print("  ✗ 403 Forbidden — this site blocks server/CI requests.")
        return None
    if not r.ok:
        print(f"  ✗ HTTP {r.status_code}")
        return None
    return r


def scrape() -> list[dict]:
    print(f"\n[Shenkar] {PAGE_URL}")
    r = get(PAGE_URL)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    anchors = soup.find_all("a", href=True)
    candidates = [a for a in anchors if JOB_HREF_RX.search(a["href"])]
    print(f"  Found {len(candidates)} Google-doc links (pre-filter)")

    for a in candidates:
        title = clean_title(a.get_text(" ", strip=True))
        if not title or not TITLE_MARKER_RX.search(title):
            continue
        url = a["href"].strip()
        if url in seen:
            continue
        seen.add(url)

        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       LOCATION,
            "date":           first_seen.get(url, TODAY),
            "url":            url,
            "department":     "academic_faculty",
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    "",   # body lives in the external Google doc (not fetched)
            "position_type":  detect_position_type(title),
        })

    print(f"  → {len(jobs)} jobs (after title-marker filter)")
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
        host = 'docs' if 'docs.google' in j['url'] else 'drive'
        print(f"  • [{j['department'][:6]}] {j['title'][:55]}  ({host})")

    print("\nNext steps:")
    print("  git add -f shenkar_jobs_*.csv")
    print("  git add fetch_shenkar.py run_fetch.bat")
    print("  git commit -m 'feat: add Shenkar college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
