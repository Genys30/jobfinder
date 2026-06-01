#!/usr/bin/env python3
"""
fetch_bgu.py — Scrapes BGU job positions from two sources:
  1. Salesforce HR portal  (bguhr.my.salesforce-sites.com)
  2. bgu.ac.il recruitment pages (pensioners + admin/technical staff)

NOTE: Both sites block requests from cloud/CI IPs (GitHub Actions).
      Run this script LOCALLY and commit the CSV manually.

Output: bgu_jobs_YYYY-MM-DD.csv
Usage:  py fetch_bgu.py
"""

import csv, re, sys
from datetime import date

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"bgu_jobs_{TODAY}.csv"
COMPANY     = "אוניברסיטת בן-גוריון בנגב"
LOCATION    = "באר שבע"

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

SALESFORCE_URL = "https://bguhr.my.salesforce-sites.com/Gius?mode=external"

BGU_PAGES = {
    "pensioners": "https://www.bgu.ac.il/recruitment/pensioners/",
    "admin":      "https://www.bgu.ac.il/recruitment/additional-jobs-administrative-and-technical-staff/",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפה לח"ל|מילוי מקום לחופשת לידה|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity|'
        r'maternity.?leave.?replace|maternity.?replace|replace\w*.?maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|חלקי\b|part.?time|part time',
        re.I | re.UNICODE
    ),
    'freelance': re.compile(
        r'פרילנס|פרי-לנס|freelance|free.?lance',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|התמחות|מתמחה|intern(ship)?|co.?op\b|trainee",
        re.I | re.UNICODE
    ),
}

def detect_position_type(title='', description=''):
    text = (title + ' ' + description).strip()
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(text):
            return pt
    return ''

def parse_date(s: str) -> str:
    """Convert DD/MM/YY or DD/MM/YYYY to ISO."""
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
    if not m:
        return TODAY
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

def get(url, referer=None):
    """GET with standard headers; returns Response or None on 403/error."""
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return None
    if r.status_code == 403:
        print(f"  ✗ 403 Forbidden — this site blocks server/CI requests.")
        print(f"    Run this script locally on your machine.")
        return None
    if not r.ok:
        print(f"  ✗ HTTP {r.status_code}")
        return None
    return r


# ── Source 1: Salesforce HR portal ────────────────────────────────────────────

def scrape_salesforce() -> list[dict]:
    print(f"\n[BGU Salesforce] {SALESFORCE_URL}")
    r = get(SALESFORCE_URL, referer="https://bguhr.my.salesforce-sites.com/")
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("table tr")
    print(f"  Found {len(rows)} table rows")

    jobs = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        if any(h in texts for h in ["שם המשרה", "מס' משרה", "Name"]):
            continue

        if len(cells) >= 4:
            title    = texts[1]
            date_str = texts[3] if len(texts) > 3 else ""
        elif len(cells) == 3:
            title    = texts[1]
            date_str = texts[2]
        else:
            continue

        if not title.strip():
            continue

        link = row.find("a", href=True)
        if link:
            href = link["href"]
            url = href if href.startswith("http") else "https://bguhr.my.salesforce-sites.com" + href
        else:
            url = SALESFORCE_URL

        jobs.append({
            "title":          title.strip(),
            "company":        COMPANY,
            "location":       LOCATION,
            "date":           parse_date(date_str) if date_str else TODAY,
            "url":            url,
            "department":     "",
            "workplace_type": "onsite",
            "source":         "bgu",
            "description":    "",
            "position_type":  detect_position_type(title),
        })

    print(f"  → {len(jobs)} jobs")
    return jobs


# ── Source 2: bgu.ac.il recruitment pages ─────────────────────────────────────

def scrape_bgu_pages() -> list[dict]:
    jobs = []
    for dept, url in BGU_PAGES.items():
        print(f"\n[BGU {dept}] {url}")
        r = get(url, referer="https://www.bgu.ac.il/recruitment/")
        if not r:
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.simple-accordion")
        print(f"  Found {len(items)} items")

        for item in items:
            title_el = item.select_one("h3.simple-accordion__name")
            body_el  = item.select_one("div.simple-accordion__body")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            desc  = body_el.get_text(" ", strip=True) if body_el else ""

            jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       LOCATION,
                "date":           TODAY,
                "url":            url,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         "bgu",
                "description":    desc[:800],
                "position_type":  detect_position_type(title, desc),
            })

    print(f"  → {len(jobs)} jobs total from bgu.ac.il pages")
    return jobs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    all_jobs = scrape_salesforce() + scrape_bgu_pages()

    if not all_jobs:
        print("\n⚠️  No jobs found — no file written.")
        sys.exit(0)

    # Deduplicate by title+url
    seen = set()
    deduped = []
    for j in all_jobs:
        k = j["title"].strip().lower() + "|" + j["url"]
        if k not in seen:
            seen.add(k)
            deduped.append(j)

    skipped = len(all_jobs) - len(deduped)
    print(f"\n✅ Wrote {len(deduped)} jobs → {OUTPUT_FILE}" +
          (f" (skipped {skipped} dupes)" if skipped else ""))

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(deduped)

    print("\nSample:")
    for j in deduped[:5]:
        print(f"  • [{j['department'] or 'salesforce'}] {j['title'][:60]}")

    print("\nNext steps:")
    print("  git add bgu_jobs_*.csv fetch_bgu.py")
    print("  git commit -m 'chore: add bgu jobs'")
    print("  git pull --rebase && git push")


if __name__ == "__main__":
    main()
