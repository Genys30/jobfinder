#!/usr/bin/env python3
"""
fetch_braude.py — Scrapes open positions at ORT Braude College of Engineering
(המכללה האקדמית להנדסה אורט בראודה, Karmiel) from the college's own "דרושים" page.

  Source: https://w3.braude.ac.il/about/jobs/
  CMS:    WordPress, server-rendered (plain requests + BeautifulSoup — no WAF,
          no Playwright). Jobs live in a Foundation accordion:
            div[id^=section-id] (section)
              ul.accordion
                li.accordion-item
                  a.accordion-title      ← title
                  div.accordion-content  ← description (inline, rich)

  Two sections on one page: משרות מנהליות (admin) / משרות אקדמיות (academic).
  This is the college's OWN open positions (employer-type: academic).

All jobs share ONE page URL (titles link to '#', apply is by email), so
first_seen is keyed by TITLE — same approach as Afeka / BGU.

Output: braude_jobs_YYYY-MM-DD.csv
Usage:  py fetch_braude.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"braude_jobs_{TODAY}.csv"
SOURCE      = "braude"
COMPANY     = "מכללת אורט בראודה"
LOCATION    = "כרמיאל"
PAGE_URL    = "https://w3.braude.ac.il/about/jobs/"

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

# Markers that prove an accordion item is a real job (guards against any other
# (non-job) accordions that may live on the page).
JOB_MARKERS = (
    "תכולת התפקיד", "תכולות התפקיד", "תיאור התפקיד", "הגדרת התפקיד",
    "דרישות", "השכלה", "כישורים", "היקף משרה", "היקף המשרה", "קורות חיים",
)

# Section heading text → department bucket.
SECTION_RX = re.compile(r'משרות\s*(מנהליות|אקדמיות)')

# ── position_type detection (same patterns as bgu / maccabi / afeka) ──────────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|מילוי מקום לחופשת לידה|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity',
        re.I | re.UNICODE
    ),
    'external_lecturer': re.compile(
        r'מרצה מן החוץ|מורה מן החוץ|מן החוץ',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|part.?time|part time',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|התמחות|מתמחה|intern(ship)?|trainee",
        re.I | re.UNICODE
    ),
}

def detect_position_type(title='', description=''):
    text = (title + ' ' + description).strip()
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(text):
            return pt
    return ''

# ── academic-vs-admin (section first, title keywords as fallback) ─────────────
ACADEMIC_RX = re.compile(
    r'מרצה|חבר.?ת? סגל|מתרגל|מדריך|פרופסור|faculty|lecturer|teaching',
    re.I | re.UNICODE
)

def detect_department(title, section_text):
    if section_text:
        if 'אקדמי' in section_text:
            return "academic_faculty"
        if 'מנהלי' in section_text:
            return "admin_staff"
    return "academic_faculty" if ACADEMIC_RX.search(title or '') else "admin_staff"


def load_first_seen():
    """Read the most recent previous braude CSV → {title: date} dict.
    All jobs share one page URL, so first_seen is keyed by TITLE (Afeka pattern)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("braude_jobs_*.csv"))
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
                t = row.get('title', '').strip()
                d = row.get('date', '').strip()
                if t and d:
                    result[t] = d
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
    print(f"\n[Braude] {PAGE_URL}")
    r = get(PAGE_URL)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    items = soup.select("li.accordion-item")
    print(f"  Found {len(items)} accordion items (pre-filter)")

    for li in items:
        title_el = li.select_one("a.accordion-title")
        if not title_el:
            continue
        title = re.sub(r'\s+', ' ', title_el.get_text(" ", strip=True)).strip()
        if not title:
            continue

        body_el = li.select_one("div.accordion-content")
        desc = body_el.get_text(" ", strip=True) if body_el else ""

        # Keep only real jobs (skip any non-job accordions on the page).
        blob = (title + " " + desc).lower()
        if not any(m.lower() in blob for m in JOB_MARKERS):
            continue

        # Section (admin / academic): nearest preceding "משרות מנהליות/אקדמיות".
        sec_node = li.find_previous(string=SECTION_RX)
        section_text = str(sec_node) if sec_node else ""

        k = title  # page-shared URL → key by title
        if k in seen:
            continue
        seen.add(k)

        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       LOCATION,
            "date":           first_seen.get(title, TODAY),
            "url":            PAGE_URL,
            "department":     detect_department(title, section_text),
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    re.sub(r'\s+', ' ', desc)[:1000],
            "position_type":  detect_position_type(title, desc),
        })

    print(f"  → {len(jobs)} jobs (after job-marker filter)")
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
    for j in jobs[:12]:
        print(f"  • [{j['department'][:6]}] {j['title'][:55]}  ({len(j['description'])} chars)")

    print("\nNext steps:")
    print("  git add -f braude_jobs_*.csv")
    print("  git add fetch_braude.py run_fetch.bat")
    print("  git commit -m 'feat: add Braude college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
