#!/usr/bin/env python3
"""
fetch_mizrahi.py — Scrapes open positions at Bank Mizrahi-Tefahot (בנק מזרחי-טפחות).

  Careers page: https://www.mizrahi-tefahot.co.il/about-mizrahi-tefahot-he/career/open-jobs/
  Platform: Custom CMS, server-rendered, NO WAF → plain requests + BS4.
  All jobs inline (~190 KB). No per-job URLs (apply via inline form on the page).
  LOCAL-ONLY (Israeli IP required).

  Card structure (div.job per job):
    div.divJobName   → title (child element — may need direct text extraction)
    div.jobDescription → description text
    div.jobMeta      → "{location} {department} {scope} הגשת מועמדות"
                       parsed into: location (first token), department (second token),
                       position_type (from scope keywords like "משרה חלקית" / "משמרות")

  No per-job URLs → first_seen + dedup by title (Braude/Afeka pattern).
  URL = page URL (canonical careers page).

Output: mizrahi_jobs_YYYY-MM-DD.csv
Usage:  py fetch_mizrahi.py
"""

import csv, re, sys, glob, time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"mizrahi_jobs_{TODAY}.csv"
SOURCE      = "mizrahi"
COMPANY     = "בנק מזרחי-טפחות"
PAGE_URL    = "https://www.mizrahi-tefahot.co.il/about-mizrahi-tefahot-he/career/open-jobs/"

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

# Strip "Live" badge and similar labels appended to some titles
TITLE_NOISE_RX = re.compile(r'\s+(Live|חדש|New|HOT)\s*$', re.I)


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def title_to_position_type(title, scope_text=""):
    combined = (title or "") + " " + (scope_text or "")
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', combined):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", combined) or re.search(r"\bintern\b", combined, re.I):
        return "internship"
    if re.search(r"סטודנט", combined):
        return "part_time"
    if re.search(r"משרה חלקית|חצי משרה|חלקית", combined):
        return "part_time"
    return ""


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("mizrahi_jobs_*.csv"))
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


def parse_meta(meta_div):
    """Parse div.jobMeta text: '{location} {dept} {scope} הגשת מועמדות'
    Returns (location, department, scope_text).
    """
    if not meta_div:
        return "ישראל", "", ""
    # Remove the apply-button text
    text = clean(meta_div.get_text(" ", strip=True))
    text = re.sub(r'הגשת מועמדות.*$', '', text).strip()
    # Remove separators like "|"
    text = re.sub(r'\|', ' ', text)
    tokens = text.split()
    if not tokens:
        return "ישראל", "", ""
    location = tokens[0] if tokens else "ישראל"
    department = tokens[1] if len(tokens) > 1 else ""
    scope_text = " ".join(tokens[2:]) if len(tokens) > 2 else ""
    return location, department, scope_text


def parse_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for div in soup.select("div.job"):
        # Skip the application form container
        if div.select_one("form, input[type='text']"):
            continue

        # Title — div.divJobName may contain nested elements
        name_el = div.select_one("div.divJobName")
        if name_el:
            title = clean(name_el.get_text(" ", strip=True))
        else:
            # Fall back: first non-empty text before "תיאור משרה"
            full_text = clean(div.get_text(" ", strip=True))
            m = re.match(r'^(.+?)(?:תיאור משרה|הגשת מועמדות)', full_text)
            title = m.group(1).strip() if m else ""
        # Strip badge suffixes
        title = TITLE_NOISE_RX.sub("", title).strip()
        if not title:
            continue

        # Description
        desc_el = div.select_one("div.jobDescription") or div.select_one("div.jobData")
        description = clean(desc_el.get_text(" ", strip=True)) if desc_el else ""

        # Meta
        meta_el = div.select_one("div.jobMeta")
        location, department, scope_text = parse_meta(meta_el)

        jobs.append({
            "title":       title,
            "location":    location or "ישראל",
            "department":  department,
            "description": description[:1500],
            "scope_text":  scope_text,
        })

    return jobs


def scrape():
    first_seen = load_first_seen()
    session = requests.Session()

    print(f"\n[Mizrahi-Tefahot] fetching {PAGE_URL} …")
    try:
        r = session.get(PAGE_URL, timeout=30, headers=HEADERS)
        if r.status_code != 200:
            print(f"  ✗ HTTP {r.status_code}")
            return []
        html = r.text
    except Exception as e:
        print(f"  ✗ {e}")
        return []

    raw_jobs = parse_jobs(html)
    print(f"  -> {len(raw_jobs)} job divs parsed")

    jobs = []
    seen_titles = set()
    for r in raw_jobs:
        title = r["title"]
        # dedup by title (no per-job URLs)
        key = title.strip()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        pt = title_to_position_type(title, r.get("scope_text", ""))
        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       r["location"],
            "date":           first_seen.get(title, TODAY),
            "url":            PAGE_URL,
            "department":     r["department"],
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    r["description"],
            "position_type":  pt,
        })
        tag = f" [{pt}]" if pt else ""
        print(f"  • {title[:52]}{tag}  | {r['location']}"
              + (f"  | {r['department']}" if r['department'] else ""))

    return jobs


def main():
    jobs = scrape()

    if not jobs:
        print("\n⚠️  No jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\n✅ Wrote {len(jobs)} jobs → {OUTPUT_FILE}")
    print("\nNext steps:")
    print("  git add -f mizrahi_jobs_*.csv")
    print("  git add fetch_mizrahi.py")
    print("  git commit -m 'feat: add Mizrahi-Tefahot careers scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
