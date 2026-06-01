"""
fetch_rambam.py  —  scraper for Rambam Health Care Campus jobs
Scrapes two pages: digital-IT jobs + general careers page.

NOTE: rambam.org.il blocks requests from cloud/CI IPs (GitHub Actions).
      Run this script LOCALLY and commit the CSV manually.

Output: rambam_jobs_YYYY-MM-DD.csv
Usage:  py fetch_rambam.py
"""

import csv, re, sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TODAY   = date.today().isoformat()
OUTFILE = Path(__file__).parent / f"rambam_jobs_{TODAY}.csv"

PAGES = [
    {
        "url": "https://www.rambam.org.il/about-rambam/careers/digital-it-jobs/",
        "department": "דיגיטל וטכנולוגיות מידע",
    },
    {
        "url": "https://www.rambam.org.il/about-rambam/careers/",
        "department": "",
    },
]

# Titles to skip — nav/placeholder/template items, not real jobs
SKIP_TITLES = {
    "משרות חטיבת הדיגיטל וטכנולוגיות המידע",
    "הגעת עד לפה ולא מצאת משרה מתאימה?",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

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

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def scrape_page(url, department):
    print(f"Fetching {url} …")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return []

    if r.status_code == 403:
        print(f"  ✗ 403 Forbidden — rambam.org.il blocks server/CI requests.")
        print(f"    Run this script locally on your machine.")
        return []

    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    jobs = []
    for item in soup.select("li.faq_item"):
        title_tag = item.select_one("h3.faq_title")
        if not title_tag:
            continue
        title = clean(title_tag.get_text())

        if not title or title in SKIP_TITLES or "{{" in title:
            continue

        desc_tag = item.select_one("div.faq_desk")
        desc = clean(desc_tag.get_text()) if desc_tag else ""

        # Find apply link (tinyurl or adamtotal)
        apply_link = ""
        if desc_tag:
            for a in desc_tag.find_all("a", href=True):
                href = a["href"]
                if "tinyurl" in href or "adamtotal" in href:
                    apply_link = href
                    break

        jobs.append({
            "title":         title,
            "company":       'הקריה הרפואית רמב"ם',
            "location":      "Haifa",
            "date":          TODAY,
            "url":           apply_link or url,
            "department":    department,
            "workplace_type": "onsite",
            "source":        "rambam",
            "description":   desc[:800],
            "position_type": detect_position_type(title, desc),
        })
    return jobs


def main():
    all_jobs = []
    seen_titles = set()

    for page in PAGES:
        jobs = scrape_page(page["url"], page["department"])
        new = [j for j in jobs if j["title"] not in seen_titles]
        for j in new:
            seen_titles.add(j["title"])
        dupes = len(jobs) - len(new)
        print(f"  → {len(new)} new jobs" + (f" (skipped {dupes} dupes)" if dupes else ""))
        all_jobs.extend(new)

    if not all_jobs:
        print("⚠️  No jobs found — no file written.")
        sys.exit(0)

    with open(OUTFILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_jobs)

    print(f"\n✅ Wrote {len(all_jobs)} jobs → {OUTFILE.name}")
    print("\nSample:")
    for j in all_jobs[:5]:
        print(f"  • [{j['department'] or 'general'}] {j['title'][:60]}")

    print("\nNext steps:")
    print("  git add rambam_jobs_*.csv")
    print("  git commit -m 'chore: add rambam jobs'")
    print("  git pull --rebase && git push")


if __name__ == "__main__":
    main()
