#!/usr/bin/env python3
"""
fetch_haifa.py — University of Haifa external open positions scraper.

Source: https://hr.haifa.ac.il/דרושים/  (external candidate jobs, WordPress/Elementor)
Each job is an <a> link to hr.haifa.ac.il/{job-number}-{slug}/ whose link text
starts with the job number followed by the title, e.g. "1126 מהנדס/ת מעבדת רכבים".

Output: haifa_jobs_{TODAY}.csv with the columns the frontend's normHaifa() expects.
"""

import csv
import glob
import re
import sys
from datetime import date, timedelta
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

TODAY = date.today().isoformat()


def load_first_seen(pattern, key_field="url"):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob(pattern))
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
                k = row.get(key_field, "").strip()
                d = row.get("date", "").strip()
                if k and d:
                    result[k] = d
    except Exception:
        pass
    return result
BASE = "https://hr.haifa.ac.il"
# URL-encoded Hebrew word "דרושים" (vacancies)
LISTING_URL = BASE + "/%d7%93%d7%a8%d7%95%d7%a9%d7%99%d7%9d/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Referer": BASE + "/",
    "Upgrade-Insecure-Requests": "1",
}
COLUMNS = [
    "title", "company", "location", "date", "deadline", "url",
    "department", "workplace_type", "description", "requirements",
]

# Job links look like /1126-..., /4426-..., /50005-... (number, dash, slug)
JOB_HREF_RE = re.compile(r"^https?://hr\.haifa\.ac\.il/\d{3,6}-")
# Leading job number in the link text
NUM_PREFIX_RE = re.compile(r"^\s*(\d{3,6})[\s\-/]+")


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"   x could not fetch {url}: {e}")
        return None


def parse(soup, first_seen):
    jobs = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not JOB_HREF_RE.match(href):
            continue
        text = a.get_text(" ", strip=True)
        if not text:
            continue
        # Skip the "submit application" links (they point to a different slug)
        if "שליחת" in href or "%d7%a9%d7%9c%d7%99%d7%97%d7%aa" in href:
            continue
        # Title text starts with the job number; strip it for a clean title
        m = NUM_PREFIX_RE.match(text)
        job_no = m.group(1) if m else ""
        title = NUM_PREFIX_RE.sub("", text).strip() if m else text
        if not title:
            continue
        key = href
        if key in seen:
            continue
        seen.add(key)
        jobs.append({
            "title": title,
            "company": "אוניברסיטת חיפה",
            "location": "חיפה",
            "date": first_seen.get(href, TODAY),
            "deadline": "",
            "url": href,
            "department": "",
            "workplace_type": "onsite",
            "description": "",
            "requirements": "",
            "_job_no": job_no,  # kept only for logging, dropped by extrasaction
        })
    return jobs


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_haifa():
    print("\n-- Haifa University -------------------------------------------------")
    first_seen = load_first_seen("haifa_jobs_*.csv", key_field="url")
    soup = fetch(LISTING_URL)
    if not soup:
        write_csv([], f"haifa_jobs_{TODAY}.csv")
        return 0
    jobs = parse(soup, first_seen)
    write_csv(jobs, f"haifa_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_haifa()
    print(f"\nDone. {count} Haifa jobs.")
    sys.exit(0)
