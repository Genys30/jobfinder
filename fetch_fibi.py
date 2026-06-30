#!/usr/bin/env python3
"""
fetch_fibi.py — Scrapes open positions at Bank FIBI (הבנק הבינלאומי הראשון).

  Pages:
    /jobsfibi/  — banking / retail jobs (company: הבנק הבינלאומי הראשון)
    /jobsmataf/ — tech / IT jobs at MATAF subsidiary (company: מת"ף - מערכות תוכנה ופרויקטים)

  Platform: custom CMS, server-rendered, NO WAF -> plain requests + BS4.
  Job structure: <section> elements (no class) within the article body.
  Each section contains: title (first significant line) + requirements/description.
  No per-job URLs — applications are by email (jobs@fibi.co.il).
  LOCAL-ONLY (Israeli IP required).

  Dedup: by title (no per-job URLs).
  URL: careers page URL (canonical).

Output: fibi_jobs_YYYY-MM-DD.csv
Usage:  py fetch_fibi.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"fibi_jobs_{TODAY}.csv"
SOURCE      = "fibi"
BASE_URL    = "https://www.fibi.co.il"

PAGES = [
    {
        "url":  BASE_URL + "/private/general/about/jobs/jobsfibi/",
        "company": "הבנק הבינלאומי הראשון",
        "label": "FIBI main",
    },
    {
        "url":  BASE_URL + "/private/general/about/jobs/jobsmataf/",
        "company": 'מת"ף',
        "label": "MATAF",
    },
]

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}

# Structural markers that delimit sections and are NOT job titles
SKIP_PHRASES = {"עמוד הבית", "משרות", "אודות", "חשבון", "פרטי", "עסקי", "פלטינום",
                "כניסה", "סגירה", "תמיכה", "footer", "header"}

# Known non-job section text fragments (boilerplate that appears after every job)
BOILERPLATE_RX = re.compile(r'קורות חיים יש לשלוח|הבנק מעודד ומקדם|הגשת מועמדות|jobs@fibi')


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות|סטודנט", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"חצי משרה|משרה חלקית|חלקית", t):
        return "part_time"
    return ""


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("fibi_jobs_*.csv"))
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
        with open(prev_file, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                t = row.get("title", "").strip()
                d = row.get("date", "").strip()
                if t and d:
                    result[t] = d
    except Exception:
        pass
    return result


def extract_jobs_from_html(html, page_url, company):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # The article body contains <section> elements, each one job
    # We skip navigation, header, footer sections
    # Try to find the main content area first
    main = (soup.find("main") or soup.find("article") or
            soup.find("div", class_=re.compile(r"content|article|main", re.I)) or
            soup.find("body"))

    for section in main.find_all("section", recursive=True):
        # Skip section if it's inside nav/header/footer
        parents = [p.name for p in section.parents]
        if any(p in parents for p in ["nav", "header", "footer"]):
            continue

        text = clean(section.get_text(" ", strip=True))
        if not text or len(text) < 30:
            continue

        # Skip boilerplate-only sections (the "how to apply" block)
        if BOILERPLATE_RX.search(text) and len(text) < 200:
            continue

        # Skip obvious nav items
        if any(phrase in text for phrase in SKIP_PHRASES):
            continue

        # Extract title: text up to first delimiter marker
        title_match = re.match(
            r'^(.+?)(?:הכישורים הנדרשים|תי?אור ה(?:תפקיד|משרה)|דרישות|היקף משרה|שעות עבודה)',
            text
        )
        if title_match:
            title = clean(title_match.group(1))
            description = clean(text[title_match.end():])
        else:
            # No delimiter: use first sentence/line as title
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not lines:
                continue
            title = clean(lines[0])[:100]
            description = clean(" ".join(lines[1:]))

        # Clean title
        title = re.sub(r'\s*–\s*$', '', title).strip()
        title = re.sub(r'\s*-\s*$', '', title).strip()
        if not title or len(title) < 5:
            continue
        if any(phrase in title for phrase in SKIP_PHRASES):
            continue

        jobs.append({
            "title":       title,
            "company":     company,
            "description": description[:1500],
            "url":         page_url,
        })

    return jobs


def scrape():
    first_seen = load_first_seen()
    session = requests.Session()
    all_jobs = []

    for page in PAGES:
        url = page["url"]
        company = page["company"]
        label = page["label"]

        print(f"\n[FIBI / {label}] fetching {url} ...")
        try:
            r = session.get(url, timeout=30, headers=HEADERS)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}")
                continue
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        raw_jobs = extract_jobs_from_html(r.text, url, company)
        print(f"  -> {len(raw_jobs)} sections parsed")

        seen = set()
        for j in raw_jobs:
            title = j["title"]
            if title in seen:
                continue
            seen.add(title)
            pt = title_to_position_type(title)
            all_jobs.append({
                "title":          title,
                "company":        company,
                "location":       "ישראל",
                "date":           first_seen.get(title, TODAY),
                "url":            url,
                "department":     "",
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    j["description"],
                "position_type":  pt,
            })
            tag = f" [{pt}]" if pt else ""
            print(f"  + {title[:55]}{tag}")

    return all_jobs


def main():
    jobs = scrape()

    if not jobs:
        print("\nNo jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\nWrote {len(jobs)} jobs -> {OUTPUT_FILE}")
    print("Next steps:")
    print("  git add -f fibi_jobs_*.csv fetch_fibi.py")
    print("  git commit -m 'feat: add FIBI careers scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
