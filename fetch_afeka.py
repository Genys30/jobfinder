#!/usr/bin/env python3
"""
fetch_afeka.py — Scrapes open positions at Afeka Tel Aviv Academic College of
Engineering from the college's own "Working at Afeka" page.

  Source: https://www.afeka.ac.il/about-afeka/general-information/jobs/
  CMS:    Umbraco, server-rendered. Jobs live in a Bootstrap accordion
          (div.accordion-item). Both tabs (admin staff / academic faculty) are
          present in the static HTML, so plain requests + BeautifulSoup is
          sufficient — no Playwright needed.

  This is the college's OWN open positions (employer-type: academic), NOT the
  "Afeka Jobs" student/alumni portal (which lists external employers).

NOTE: .il sites often block cloud/CI IPs (403). Run this LOCALLY via
      run_fetch.bat and commit the CSV manually.

All jobs share ONE page URL (no per-job permalink), so first_seen is keyed by
TITLE — same approach as BGU's bgu.ac.il pages.

Output: afeka_jobs_YYYY-MM-DD.csv
Usage:  py fetch_afeka.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"afeka_jobs_{TODAY}.csv"
SOURCE      = "afeka"
COMPANY     = "מכללת אפקה"
LOCATION    = "תל אביב"
PAGE_URL    = "https://www.afeka.ac.il/about-afeka/general-information/jobs/"

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

# Markers that prove an accordion item is a real job (not an events accordion).
JOB_MARKERS = (
    "תיאור התפקיד", "תיאור תפקיד", "תיאור המשרה", "דרישות התפקיד", "דרישות",
    "להגשת קורות חיים", "להגשת קרות חיים", "קורות חיים",
    "requirements", "responsibilities", "description", "send cv",
)

# ── position_type detection (same patterns as bgu / maccabi) ──────────────────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|מילוי מקום לחופשת לידה|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|part.?time|part time',
        re.I | re.UNICODE
    ),
    'freelance': re.compile(
        r'פרילנס|פרי-לנס|freelance|free.?lance',
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

# ── academic-vs-admin heuristic (the page has two tabs) ───────────────────────
# Match real academic faculty only. A lone "מהנדס"/"engineer" is NOT academic
# (e.g. a lab-operations technician), so it's intentionally excluded.
ACADEMIC_RX = re.compile(
    r'סגל אקדמי|חבר.?ת? סגל|חברת סגל|מרצה|פרופסור|דוקטורט|'
    r'faculty member|teaching position|lecturer|professor|'
    r'doctorate|ph\.?d|tenure',
    re.I | re.UNICODE
)

def detect_department(title='', description=''):
    text = (title + ' ' + description)
    return "academic_faculty" if ACADEMIC_RX.search(text) else "admin_staff"


def load_first_seen():
    """Read the most recent previous afeka CSV → {title: date} dict.
    All jobs share one page URL, so first_seen is keyed by TITLE (BGU pattern)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("afeka_jobs_*.csv"))
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
        print("    Run this script locally on your machine.")
        return None
    if not r.ok:
        print(f"  ✗ HTTP {r.status_code}")
        return None
    return r


def scrape() -> list[dict]:
    print(f"\n[Afeka] {PAGE_URL}")
    r = get(PAGE_URL)
    if not r:
        return []

    soup  = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.accordion-item")
    print(f"  Found {len(items)} accordion items (pre-filter)")

    first_seen = load_first_seen()
    jobs = []
    seen = set()

    for item in items:
        title_el = item.select_one(".accordion-header button") \
                   or item.select_one(".accordion-header")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        if not title:
            continue

        body_el = item.select_one(".accordion-collapse")
        desc = body_el.get_text(" ", strip=True) if body_el else ""

        # Keep only real jobs (skip events / other faq accordions on the page).
        blob = (title + " " + desc).lower()
        if not any(m.lower() in blob for m in JOB_MARKERS):
            continue

        # Apply link: first http(s) <a> in the body, else fall back to the page.
        url = PAGE_URL
        if body_el:
            for a in body_el.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http"):
                    url = href
                    break

        k = title + "|" + url
        if k in seen:
            continue
        seen.add(k)

        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       LOCATION,
            "date":           first_seen.get(title, TODAY),
            "url":            url,
            "department":     detect_department(title),
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    desc[:800],
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
    for j in jobs[:8]:
        print(f"  • [{j['department']}] {j['title'][:60]}")

    print("\nNext steps:")
    print("  git add -f afeka_jobs_*.csv")
    print("  git add fetch_afeka.py run_fetch.bat")
    print("  git commit -m 'feat: add Afeka college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
