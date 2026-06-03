#!/usr/bin/env python3
"""
fetch_ichilov.py — Ichilov / Tel Aviv Sourasky Medical Center (איכילוב) scraper.

Source: RedMatch / TopMatch candidate API (same platform as Bar-Ilan & Clalit):
    POST https://careers.topmatch.co.il/CandidateAPI/api//position/Search/{GUID}
    body: {"KeyWords": "", "CategoryId": [], "countryId": 2, "cityId": []}

The GUID 3FC41CB2-A7A8-454A-BC2B-0EDC1A919656 is Ichilov's (TASMC) affiliate ID.
Response has a "positions" array (compPositionID, jobTitleText, displayLocation,
fieldDesc, description HTML, activationDate, scheduleExpirationDate).

Output: topmatch_jobs_{TODAY}.csv — the frontend's loadIchilov() reads this file
via normIchilov() (columns: title, company, location, date, url, department, description).

Pure requests (no Playwright). 403 from non-Israeli IPs — runs locally.
"""

import csv
import html
import re
import sys
from datetime import date

import requests

TODAY = date.today().isoformat()
AFFILIATE_GUID = "3FC41CB2-A7A8-454A-BC2B-0EDC1A919656"
SEARCH_URL = (
    "https://careers.topmatch.co.il/CandidateAPI/api//position/Search/"
    + AFFILIATE_GUID
)
APPLY_BASE = "https://jobs.tasmc.org.il/Positions"
POSITION_URL = APPLY_BASE + "/redmatch-apply/redmatch.apply.html?compPositionID={id}"
COMPANY = "המרכז הרפואי תל-אביב (איכילוב)"
DEFAULT_CITY = "Tel Aviv"
PAYLOAD = {"KeyWords": "", "CategoryId": [], "countryId": 2, "cityId": []}
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://jobs.tasmc.org.il",
    "Referer": APPLY_BASE + "/",
}
COLUMNS = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "description",
]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")


def strip_html(raw):
    if not raw:
        return ""
    text = raw.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"</(p|li|ul|h1|h2|h3|div)>", "\n", text, flags=re.I)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    lines = [WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def iso_date(s):
    if not s:
        return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def fetch():
    try:
        r = requests.post(SEARCH_URL, json=PAYLOAD, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"   x could not fetch Ichilov positions: {e}")
        return None


def parse(data):
    jobs = []
    for p in (data or {}).get("positions", []) or []:
        if not p.get("isActivePosition", True):
            continue
        pid = p.get("compPositionID")
        title = (p.get("jobTitleText") or "").strip().strip("*").strip()
        if not title or pid is None:
            continue
        jobs.append({
            "title": title,
            "company": COMPANY,
            "location": (p.get("displayLocation") or p.get("location") or DEFAULT_CITY).strip(),
            "date": iso_date(p.get("activationDate")) or TODAY,
            "url": POSITION_URL.format(id=pid),
            "department": (p.get("fieldDesc") or "").strip(),
            "workplace_type": "onsite",
            "description": strip_html(p.get("description")),
        })
    return jobs


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_ichilov():
    print("\n-- Ichilov / TASMC (איכילוב) ----------------------------------------")
    data = fetch()
    jobs = parse(data)
    write_csv(jobs, f"topmatch_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_ichilov()
    print(f"\nDone. {count} Ichilov jobs.")
    sys.exit(0)
