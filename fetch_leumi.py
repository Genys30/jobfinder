#!/usr/bin/env python3
"""
fetch_leumi.py — Scrapes open positions at Bank Leumi (בנק לאומי).

  Careers search page: https://www.leumi.co.il/he/leumi_main/searchjobs
  Platform: Drupal 11, server-rendered, NO WAF → plain requests + BS4.
  All jobs are rendered inline on the searchjobs page (~330 KB, 28+ jobs).
  No pagination detected (single page, all results).
  LOCAL-ONLY (Israeli IP required; searchjobs may return empty from datacenter).

  Card structure (div.full-job per job):
    div.job-title         → title
    div.job-content a     → detail URL (/he/Articles/{id}) — dedup/first_seen key
    div.job-content text  → "מערך/חטיבה: {division}" → department
    div[class*='area']    → "אזור: {location}" (may be absent → fallback "ישראל")
    div.job-description-text  → description body
    div.job-requirements-text → requirements (appended to description)

Output: leumi_jobs_YYYY-MM-DD.csv
Usage:  py fetch_leumi.py
"""

import csv, re, sys, glob, time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"leumi_jobs_{TODAY}.csv"
SOURCE      = "leumi"
COMPANY     = "בנק לאומי"
BASE        = "https://www.leumi.co.il"
SEARCH_URL  = BASE + "/he/leumi_main/searchjobs"

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


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"סטודנט", t):
        return "part_time"
    if re.search(r"חצי משרה|משרה חלקית|חלקית", t):
        return "part_time"
    return ""


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("leumi_jobs_*.csv"))
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
                u = row.get("url", "").strip()
                d = row.get("date", "").strip()
                if u and d:
                    result[u] = d
    except Exception:
        pass
    return result


def fetch_page(session, url):
    try:
        r = session.get(url, timeout=30, headers=HEADERS)
        if r.status_code == 200:
            return r.text
        print(f"  ✗ {url} — HTTP {r.status_code}")
    except Exception as e:
        print(f"  ✗ {url} — {e}")
    return None


def parse_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for div in soup.select("div.full-job"):
        # Title
        title_el = div.select_one("div.job-title")
        title = clean(title_el.get_text(" ", strip=True)) if title_el else ""
        if not title:
            continue

        # URL — prefer /he/Articles/... link inside job-content or full-job
        url = ""
        for a in div.find_all("a", href=True):
            href = a["href"]
            if "/he/Articles/" in href or "/he/node/" in href:
                if href.startswith("/"):
                    href = BASE + href
                # Skip share/email links
                if "facebook" in href or "mailto" in href or "linkedin" in href:
                    continue
                url = href
                break
        if not url:
            continue

        # Department — "מערך/חטיבה: ..." in job-content text
        department = ""
        content_el = div.select_one("div.job-content")
        if content_el:
            ct = clean(content_el.get_text(" ", strip=True))
            m = re.search(r'מערך[/]?חטיבה\s*[:\-]\s*(.+)', ct)
            if m:
                department = m.group(1).strip()

        # Location — "אזור: ..." in a div with 'area' in its class
        location = ""
        for el in div.find_all(True):
            classes = " ".join(el.get("class", []))
            if "area" in classes.lower():
                txt = clean(el.get_text(" ", strip=True))
                txt = re.sub(r'^אזור\s*[:\-]\s*', '', txt)
                if txt:
                    location = txt
                    break
        if not location:
            location = "ישראל"

        # Description = body + requirements
        desc_parts = []
        desc_el = div.select_one("div.job-description-text")
        if desc_el:
            desc_parts.append(clean(desc_el.get_text(" ", strip=True)))
        req_el = div.select_one("div.job-requirements-text")
        if req_el:
            req_text = clean(req_el.get_text(" ", strip=True))
            if req_text:
                desc_parts.append("דרישות: " + req_text)
        description = " | ".join(desc_parts)[:1500]

        jobs.append({
            "title":    title,
            "url":      url,
            "location": location,
            "department": department,
            "description": description,
        })

    return jobs


def scrape():
    first_seen = load_first_seen()
    session = requests.Session()

    print(f"\n[Bank Leumi] fetching {SEARCH_URL} …")
    html = fetch_page(session, SEARCH_URL)
    if not html:
        print("  ✗ Failed to fetch search page")
        return []

    raw_jobs = parse_jobs(html)
    print(f"  → {len(raw_jobs)} job divs parsed")

    jobs = []
    seen_urls = set()
    for r in raw_jobs:
        url = r["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title = r["title"]
        pt = title_to_position_type(title)
        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       r["location"],
            "date":           first_seen.get(url, TODAY),
            "url":            url,
            "department":     r["department"],
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    r["description"],
            "position_type":  pt,
        })
        tag = f" [{pt}]" if pt else ""
        print(f"  • {title[:52]}{tag}  | {r['location']}"
              + (f"  | {r['department'][:30]}" if r['department'] else ""))

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
    print("  git add -f leumi_jobs_*.csv")
    print("  git add fetch_leumi.py run_fetch.bat")
    print("  git commit -m 'feat: add Bank Leumi careers scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
