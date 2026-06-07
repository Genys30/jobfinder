#!/usr/bin/env python3
"""
fetch_tau.py — Tel Aviv University open positions scraper.

The Hebrew page https://www.tau.ac.il/positions renders job rows directly in
the HTML as a Drupal views-table (the english. subdomain loads them via AJAX,
so we use the Hebrew one). Two tabs:
  qt-jobs_tabs=0 -> administrative staff (משרות סגל מנהלי)
  qt-jobs_tabs=1 -> academic staff       (משרות סגל אקדמי)

Output: tau_jobs_{TODAY}.csv with the columns the frontend's normTAU() expects.
"""

import csv
import glob
import re
import sys
import time
from datetime import date, timedelta

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
BASE = "https://www.tau.ac.il"
TABS = {
    "0": "administrative",  # משרות סגל מנהלי
    "1": "academic",        # משרות סגל אקדמי
}
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
    "department", "workplace_type", "staff_type", "internal_external",
    "description", "requirements",
]


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url):
    try:
        # Warm up the session so the site sets cookies like a real browser
        r = SESSION.get(url, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"   x could not fetch {url}: {e}")
        return None


def parse_tab(soup, staff_type):
    """Extract job rows from one quicktab's views-table."""
    jobs = []
    for table in soup.select("table.views-table"):
        for tr in table.select("tbody tr"):
            title_cell = tr.select_one("td.views-field-title a")
            if not title_cell:
                continue
            title = title_cell.get_text(" ", strip=True)
            href = title_cell.get("href", "")
            if not title or not href:
                continue
            url = href if href.startswith("http") else BASE + href

            dept_cell = tr.select_one("td.views-field-field-position-department")
            department = dept_cell.get_text(" ", strip=True) if dept_cell else ""

            type_cell = tr.select_one("td.views-field-field-position-type")
            internal_external = type_cell.get_text(" ", strip=True) if type_cell else ""

            # Deadline: machine-readable date sits in the dc:date content attr
            deadline = ""
            date_span = tr.select_one("span.date-display-single")
            if date_span:
                content = date_span.get("content", "")
                m = re.search(r"(\d{4}-\d{2}-\d{2})", content)
                if m:
                    deadline = m.group(1)
                else:
                    deadline = date_span.get_text(strip=True)

            jobs.append({
                "title": title,
                "company": "אוניברסיטת תל אביב",
                "location": "תל אביב",
                "date": first_seen.get(url, TODAY),
                "deadline": deadline,
                "url": url,
                "department": department,
                "workplace_type": "onsite",
                "staff_type": staff_type,
                "internal_external": internal_external,
                "description": "",
                "requirements": "",
            })
    return jobs


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_tau():
    print("\n-- TAU (Tel Aviv University) ---------------------------------------")
    first_seen = load_first_seen("tau_jobs_*.csv", key_field="url")
    all_jobs = []
    seen = set()
    for tab, staff_type in TABS.items():
        url = f"{BASE}/positions?qt-jobs_tabs={tab}"
        soup = fetch(url)
        if not soup:
            continue
        rows = parse_tab(soup, staff_type)
        new = 0
        for j in rows:
            key = j["url"] or (j["company"] + "|" + j["title"])
            if key in seen:
                continue
            seen.add(key)
            all_jobs.append(j)
            new += 1
        print(f"   tab {tab} ({staff_type}): +{new}")
        time.sleep(0.5)

    write_csv(all_jobs, f"tau_jobs_{TODAY}.csv")
    return len(all_jobs)


if __name__ == "__main__":
    count = run_tau()
    print(f"\nDone. {count} TAU jobs.")
    sys.exit(0 if count >= 0 else 1)
