#!/usr/bin/env python3
"""
fetch_yvc.py — Scrapes open positions at the Max Stern Yezreel Valley College
(המכללה האקדמית עמק יזרעאל / YVC) from the college's own "דרושים" page.

  Source: https://www.yvc.ac.il/jobs/
  CMS:    WordPress (theme "emek"), server-rendered, NO WAF → requests + BS4.

  NOTE: source key is `yvc` (not `emek`) because EMEK_JOBS already exists in the
  frontend for HaEmek Medical Center (the Afula hospital). yvc = the college's
  own domain/abbreviation, avoids the name collision.

  Jobs live in a single accordion:
    section.q-and-a
      div.question-item                         ← one job
        a.question-link > span                  ← toggle title (generic, repeats!)
        div.collapse > div.sub-question > div.answer
          <p><strong><u>… לקורס</u></strong>: COURSE</p>   ← 1st <p>: label + course
          <p>משרת חבר.ת סגל אקדמי</p> …                     ← hours, schedule, email…

  DUPLICATE-TITLE gotcha (like HIT): the toggle text repeats across jobs (e.g.
  two "… מחפש מרצה / מתרגל.ת לקורס"); the distinguishing course name lives in the
  body's first <p>. So the title is ENRICHED with the course name → unique and
  informative. The #questionN anchor is sequential (render order), NOT stable,
  so it is NOT used as a key. No per-job URL (apply by email) → first_seen /
  dedup by the enriched TITLE (Afeka/Braude pattern).

  Scope = academic + admin (Anna's choice for general colleges); department is
  inferred from keywords (חבר סגל / מרצה / מתרגל → academic, else admin). The
  page currently lists only academic course positions.

Output: yvc_jobs_YYYY-MM-DD.csv
Usage:  py fetch_yvc.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"yvc_jobs_{TODAY}.csv"
SOURCE      = "yvc"
COMPANY     = "המכללה האקדמית עמק יזרעאל"
LOCATION    = "עמק יזרעאל"
PAGE_URL    = "https://www.yvc.ac.il/jobs/"

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

ACADEMIC_RX = re.compile(
    r'חבר.?ת? סגל|סגל אקדמי|מרצה|מתרגל|מרצים|מנחה|פרופסור|חוקר|דוקטור',
    re.I | re.UNICODE
)

# ── position_type (ONLY frontend-known values; else '' → full_time) ───────────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|'
        r'מילוי מקום לחופשת לידה|ממלא.?ת? מקום|maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|חצי משרה|\b50%\b|\b25%\b|\b60%\b|\b75%\b|part.?time',
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


def clean(t):
    return re.sub(r'\s+', ' ', (t or '')).strip()


def build_title(toggle, answer_el):
    """Enrich the (repeating) toggle title with the course name from the body's
    first <p>, so duplicate toggles become unique."""
    toggle = clean(toggle)
    course = ''
    if answer_el:
        p1 = answer_el.find('p')
        if p1:
            t1 = clean(p1.get_text(" ", strip=True))
            # first <p> is "…לקורס: COURSE" — course is the text after the colon
            if ':' in t1:
                course = t1.split(':', 1)[1].strip()
            elif t1 and t1 != toggle:
                course = t1
    if course and course not in toggle:
        return f"{toggle}: {course}"
    return toggle


def load_first_seen():
    """Read the most recent previous yvc CSV → {title: date} dict.
    No per-job URL → first_seen keyed by (enriched) TITLE."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("yvc_jobs_*.csv"))
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
    if not r.ok:
        print(f"  ✗ HTTP {r.status_code}")
        return None
    return r


def scrape() -> list[dict]:
    print(f"\n[YVC / Emek Yezreel] {PAGE_URL}")
    r = get(PAGE_URL)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    items = soup.select("section.q-and-a div.question-item")
    if not items:
        items = soup.select("div.question-item")
    print(f"  Found {len(items)} question-item blocks")

    for item in items:
        toggle_el = item.select_one("a.question-link span") or item.select_one("a.question-link")
        answer_el = item.select_one("div.answer")
        if not toggle_el:
            continue

        title = build_title(toggle_el.get_text(" ", strip=True), answer_el)
        if not title:
            continue

        desc = clean(answer_el.get_text(" ", strip=True)) if answer_el else ""

        if title in seen:
            continue
        seen.add(title)

        dept = "academic_faculty" if ACADEMIC_RX.search(title + " " + desc) else "admin_staff"

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

    print(f"  → {len(jobs)} jobs total")
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
        print(f"  • [{j['department'][:6]}] {j['title'][:60]}{pt}  ({len(j['description'])} chars)")

    print("\nNext steps:")
    print("  git add -f yvc_jobs_*.csv")
    print("  git add fetch_yvc.py run_fetch.bat")
    print("  git commit -m 'feat: add Emek Yezreel (YVC) college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
