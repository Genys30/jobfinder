#!/usr/bin/env python3
"""
fetch_migdal.py — Scrapes open positions at Migdal Insurance (מגדל).

  Site:   my.migdal.co.il/about/jobs
  API:    my.migdal.co.il/data/api/ContentData/FrontContentData/?ListType=Jobs&Source=content
  Tech:   JSON REST API — returns all jobs in one call, no pagination.
  WAF:    None.
  Dedup:  by numberJob (job ID embedded in URL fragment).
  LOCAL-ONLY (run via run_fetch.bat).

Output: migdal_jobs_YYYY-MM-DD.csv
Usage:  py fetch_migdal.py
"""

import csv, glob, re, sys
from datetime import date, timedelta
from html.parser import HTMLParser

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"migdal_jobs_{TODAY}.csv"
SOURCE      = "migdal"
COMPANY     = "מגדל"
BASE_URL    = "https://my.migdal.co.il"
API_URL     = BASE_URL + "/data/api/ContentData/FrontContentData/?ListType=Jobs&Source=content"

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "he-IL,he;q=0.9",
    "Referer": BASE_URL + "/about/jobs",
}


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
    def handle_data(self, d):
        self._parts.append(d)
    def get_text(self):
        return " ".join(self._parts)


def strip_html(html):
    s = _HTMLStripper()
    s.feed(html or "")
    return re.sub(r"\s+", " ", s.get_text()).strip()


def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"חצי משרה|משרה חלקית|חלקית|חלקי|סטודנט", t):
        return "part_time"
    return ""


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("migdal_jobs_*.csv"))
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


def scrape():
    first_seen = load_first_seen()

    print(f"[Migdal] fetching {API_URL} ...")
    r = requests.get(API_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    payload = r.json()
    raw = payload.get("Data", [])
    print(f"  API returned {len(raw)} items")

    jobs = []
    for j in raw:
        title = (j.get("jobTitle") or j.get("_name") or "").strip()
        if not title:
            continue
        num = (j.get("numberJob") or "").strip()
        url = f"{BASE_URL}/about/jobs#{num}" if num else BASE_URL + "/about/jobs"

        location = (j.get("jobLocation") or "").strip()

        area_list = j.get("jobArea") or []
        department = area_list[0]["_name"].strip() if area_list else ""

        desc_html = (j.get("jobDescription") or "") + " " + (j.get("requirements") or "")
        description = strip_html(desc_html)[:1500]

        pt = title_to_position_type(title)

        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       location or "פתח תקווה",
            "date":           first_seen.get(url, TODAY),
            "url":            url,
            "department":     department,
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    description,
            "position_type":  pt,
        })
        tag = f" [{pt}]" if pt else ""
        print(f"  {title[:55]}{tag}")

    return jobs


def main():
    jobs = scrape()

    if not jobs:
        print("No jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\nWrote {len(jobs)} jobs -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
