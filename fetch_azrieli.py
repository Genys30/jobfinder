#!/usr/bin/env python3
"""
fetch_azrieli.py — Scrapes open positions at the Azrieli College of Engineering
Jerusalem (המכללה האקדמית להנדסה ירושלים ע"ש עזריאלי / JCE) from the college's
own "דרושים" page.

  Source: https://www.jce.ac.il/possitions/   (note: the live URL is "possitions")
  CMS:    WordPress (theme roots-mipo), server-rendered. BUT plain requests get a
          403 block page (~5 KB) → use curl_cffi `chrome110` TLS impersonation
          (200, ~182 KB), like Osem/HIT. Warm-up on home page + retries.

  Jobs live in a custom accordion split across TWO sections:
    div#academic-staff       →  academic (סגל אקדמי)
    div#administrative-staff →  admin    (סגל מנהלי)
  Each job: div.unit
              div.unit_name > h3   ← title
              div.unit_content     ← description (inline, rich → pop-up works)

  This is the college's OWN open positions (employer-type: academic).

No per-job URL (accordion toggles in-page, apply by email), so first_seen is
keyed by TITLE — same approach as Afeka / Braude / BGU.

Output: azrieli_jobs_YYYY-MM-DD.csv
Usage:  py fetch_azrieli.py
"""

import csv, re, sys, glob, time
from datetime import date, timedelta

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("curl_cffi not installed. Run: pip install curl_cffi")
    sys.exit(1)

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"azrieli_jobs_{TODAY}.csv"
SOURCE      = "azrieli"
COMPANY     = "מכללת עזריאלי להנדסה ירושלים"
LOCATION    = "ירושלים"
PAGE_URL    = "https://www.jce.ac.il/possitions/"

# Section container id → department bucket.
SECTION_DEPARTMENT = {
    "academic-staff":       "academic_faculty",
    "administrative-staff": "admin_staff",
}

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

# ── position_type detection (ONLY values the frontend Contract filter knows:
#    maternity_cover / part_time / freelance / internship; else '' → full_time) ──
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|'
        r'מילוי מקום לחופשת לידה|ממלא.?ת? מקום|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|חצי משרה|part.?time|part time',
        re.I | re.UNICODE
    ),
    'freelance': re.compile(
        r'פרילנס|פרי-לנס|freelance|free.?lance',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|מתמחה|\bintern\b|\binternship\b|\btrainee\b",
        re.I | re.UNICODE
    ),
}

def detect_position_type(title='', description=''):
    text = (title + ' ' + description).strip()
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(text):
            return pt
    return ''


def clean_title(t):
    t = re.sub(r'\s+', ' ', (t or '')).strip()
    return t


def load_first_seen():
    """Read the most recent previous azrieli CSV → {title: date} dict.
    No per-job URL → first_seen keyed by TITLE (Afeka/Braude pattern)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("azrieli_jobs_*.csv"))
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


def fetch_html():
    """curl_cffi with chrome110 TLS impersonation clears the WAF 403. Warm up on
    the home page first, then fetch /possitions/. Retries on timeout/5xx."""
    session = cffi_requests.Session(impersonate="chrome110")
    try:
        session.get("https://www.jce.ac.il/", timeout=30)
        time.sleep(1.5)
    except Exception as e:
        print(f"  (warm-up skipped: {e})")

    last = None
    for attempt in range(1, 4):
        try:
            r = session.get(PAGE_URL, timeout=45)
            if r.status_code == 200 and r.text:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        print(f"  attempt {attempt}/3 failed: {last} — retrying…")
        time.sleep(2.5)
    print(f"  ✗ giving up after 3 attempts: {last}")
    return None


def scrape() -> list[dict]:
    print(f"\n[Azrieli] {PAGE_URL}")
    html = fetch_html()
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    for sec_id, dept in SECTION_DEPARTMENT.items():
        sec = soup.find(id=sec_id)
        if not sec:
            print(f"  [{dept}] section #{sec_id} not found")
            continue
        units = sec.select("div.unit")
        print(f"  [{dept}] {len(units)} units")

        for unit in units:
            title_el = unit.select_one("div.unit_name h3") or unit.select_one("h3")
            if not title_el:
                continue
            title = clean_title(title_el.get_text(" ", strip=True))
            if not title:
                continue

            body_el = unit.select_one("div.unit_content")
            desc = body_el.get_text(" ", strip=True) if body_el else ""
            desc = re.sub(r'\s+', ' ', desc).strip()

            k = title  # in-page accordion → key by title
            if k in seen:
                continue
            seen.add(k)

            jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       LOCATION,
                "date":           first_seen.get(title, TODAY),
                "url":            PAGE_URL,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    desc[:1000],
                "position_type":  detect_position_type(title, desc),
            })

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
        print(f"  • [{j['department'][:6]}] {j['title'][:50]}{pt}  ({len(j['description'])} chars)")

    print("\nNext steps:")
    print("  git add -f azrieli_jobs_*.csv")
    print("  git add fetch_azrieli.py run_fetch.bat")
    print("  git commit -m 'feat: add Azrieli college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
