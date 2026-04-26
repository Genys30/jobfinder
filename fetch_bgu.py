#!/usr/bin/env python3
"""
fetch_bgu.py — Scrapes external job positions from BGU Salesforce site.
URL: https://bguhr.my.salesforce-sites.com/Gius?mode=external
Outputs bgu_jobs_YYYY-MM-DD.csv
"""

import csv
import re
import sys
from datetime import date

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"bgu_jobs_{TODAY}.csv"
URL         = "https://bguhr.my.salesforce-sites.com/Gius?mode=external"
FIELDNAMES  = ["title", "company", "location", "date", "url",
               "department", "workplace_type", "source"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Referer": "https://bguhr.my.salesforce-sites.com/",
}


def parse_date(s: str) -> str:
    """Convert DD/MM/YY or DD/MM/YYYY to ISO."""
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
    if not m:
        return TODAY
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"


def scrape() -> list[dict]:
    print(f"[bgu] Fetching {URL}")
    try:
        r = requests.get(URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[bgu] ERROR: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []

    # Find all table rows — each job is a <tr> with cells:
    # מס' משרה | שם המשרה | הגשת מועמדות (link) | תאריך
    rows = soup.select("table tr")
    print(f"[bgu] Found {len(rows)} table rows")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # Try to find the job title and apply link
        title = ""
        url   = ""
        date_str = ""
        job_id = ""

        texts = [c.get_text(strip=True) for c in cells]

        # Skip header rows
        if any(h in texts for h in ["שם המשרה", "מס' משרה", "Name"]):
            continue

        # Column order: ID | title | apply-link | date
        if len(cells) >= 4:
            job_id   = texts[0]
            title    = texts[1]
            date_str = texts[3] if len(texts) > 3 else ""
        elif len(cells) == 3:
            job_id   = texts[0]
            title    = texts[1]
            date_str = texts[2]

        # Get apply URL from link in row
        link = row.find("a", href=True)
        if link:
            href = link.get("href", "")
            url = href if href.startswith("http") else "https://bguhr.my.salesforce-sites.com" + href

        if not title or not title.strip():
            continue

        # Use job detail page URL or fallback to main URL
        if not url:
            url = URL

        jobs.append({
            "title":          title.strip(),
            "company":        "אוניברסיטת בן-גוריון בנגב",
            "location":       "באר שבע",
            "date":           parse_date(date_str) if date_str else TODAY,
            "url":            url,
            "department":     "",
            "workplace_type": "onsite",
            "source":         "bgu",
        })

    return jobs


def main():
    jobs = scrape()
    if not jobs:
        print("[bgu] No jobs found — no file written.")
        return

    # Deduplicate
    seen = set()
    deduped = []
    for j in jobs:
        k = j["title"] + j["url"]
        if k not in seen:
            seen.add(k)
            deduped.append(j)

    print(f"[bgu] {len(deduped)} jobs → {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(deduped)
    print("[bgu] Done.")


if __name__ == "__main__":
    main()
