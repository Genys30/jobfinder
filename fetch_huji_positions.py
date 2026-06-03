#!/usr/bin/env python3
"""
fetch_huji_positions.py — Hebrew University of Jerusalem internal vacancies.

Source: HunterHRMS portal https://huji.hunterhrms.com/search-results/
Server-rendered HTML (pure requests, no Playwright). Listing has .job-wrap blocks
with a label.job-title (for=jobcode). Descriptions live at /job-details/?jobcode=.

Output: huji_positions_{TODAY}.csv (columns the frontend's normHujiPositions expects:
title, campus, url, date, deadline, department, description, requirements).

403 from non-Israeli IPs — runs locally.
"""

import csv
import re
import sys
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

TODAY = date.today().isoformat()
BASE = "https://huji.hunterhrms.com"
SEARCH_URL = BASE + "/search-results/"
COMPANY = "האוניברסיטה העברית בירושלים"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Referer": BASE + "/",
}
COLUMNS = [
    "title", "company", "location", "date", "deadline", "url",
    "jobcode", "campus", "department", "workplace_type",
    "description", "requirements",
]


def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"   [warn] {e}")
        return None


def parse_deadline(s):
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return ""


def fetch_description(jobcode):
    url = f"{BASE}/job-details/?jobcode={jobcode}"
    soup = fetch_page(url)
    if not soup:
        return "", "", url
    desc, reqs = "", ""
    full = soup.get_text("\n", strip=True)
    for marker in ["תיאור המשרה", "תיאור התפקיד:"]:
        if marker in full:
            after = full.split(marker, 1)[1]
            for stop in ["דרישות המשרה", "דרישות התפקיד:", "הערות", "כפיפות:"]:
                if stop in after:
                    after = after.split(stop, 1)[0]
            desc = after.strip()
            break
    for marker in ["דרישות המשרה", "דרישות התפקיד:"]:
        if marker in full:
            after = full.split(marker, 1)[1]
            for stop in ["הערות", "כפיפות:", "היקף משרה:", "במסגרת מדיניות"]:
                if stop in after:
                    after = after.split(stop, 1)[0]
            reqs = after.strip()
            break
    return desc, reqs, url


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_huji_positions():
    print("\n-- HUJI Positions (האוניברסיטה העברית בירושלים) ----------------------")
    soup = fetch_page(SEARCH_URL)
    if not soup:
        print("   x could not fetch HUJI positions page")
        write_csv([], f"huji_positions_{TODAY}.csv")
        return 0

    jobs = []
    seen = set()
    for wrap in soup.select(".job-wrap"):
        label = wrap.select_one("label.job-title")
        if not label:
            continue
        jobcode = label.get("for", "").strip()
        if not jobcode or jobcode in seen:
            continue
        seen.add(jobcode)
        title = re.sub(r"\s+", " ", label.get_text(strip=True)).strip()
        campus_el = wrap.select_one("p.kampus")
        campus = campus_el.get_text(strip=True) if campus_el else "ירושלים"
        deadline_raw = ""
        for el in wrap.select(".last-date, .date"):
            t = el.get_text(strip=True)
            if re.search(r"\d{2}/\d{2}/\d{4}", t):
                deadline_raw = t
                break
        jobs.append({
            "title": title, "company": COMPANY, "location": "ירושלים",
            "date": TODAY, "deadline": parse_deadline(deadline_raw),
            "jobcode": jobcode, "campus": campus, "department": "",
            "workplace_type": "onsite", "description": "", "requirements": "",
            "url": "",
        })

    print(f"   Found {len(jobs)} listings — fetching descriptions...")
    for i, job in enumerate(jobs, 1):
        desc, reqs, url = fetch_description(job["jobcode"])
        job["description"] = desc
        job["requirements"] = reqs
        job["url"] = url
        print(f"   [{i}/{len(jobs)}] {job['title'][:60]}")
        time.sleep(0.4)

    write_csv(jobs, f"huji_positions_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_huji_positions()
    print(f"\nDone. {count} HUJI positions.")
    sys.exit(0)
