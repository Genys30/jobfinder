#!/usr/bin/env python3
"""
fetch_bar.py — Bar-Ilan University (BIU) open positions scraper.

Source: RedMatch / TopMatch candidate API used by careers.topmatch.co.il/biu/
The public job board is a JS shell; the data comes from a POST endpoint:

    POST https://careers.topmatch.co.il/CandidateAPI/api//position/Search/{AFFILIATE_GUID}
    body: {"KeyWords": "", "CategoryId": [], "countryId": 2, "cityId": []}

The GUID D8D6FFC7-31E2-46C1-94B4-985C99B9A913 is BIU's affiliate ID.
Response JSON has a "positions" array; each item has compPositionID, jobTitleText,
activationDate, displayLocation, fieldDesc, description (HTML), scheduleExpirationDate.

Output: bar_jobs_{TODAY}.csv with the columns the frontend's normBAR() expects.
"""

import csv
import html
import re
import sys
from datetime import date

import requests

TODAY = date.today().isoformat()
AFFILIATE_GUID = "D8D6FFC7-31E2-46C1-94B4-985C99B9A913"
SEARCH_URL = (
    "https://careers.topmatch.co.il/CandidateAPI/api//position/Search/"
    + AFFILIATE_GUID
)
# Public-facing per-position page (what a candidate sees / where they apply)
POSITION_URL = (
    "https://careers.topmatch.co.il/biu/redmatch-apply/"
    "redmatch.apply.html?compPositionID={id}"
)
PAYLOAD = {"KeyWords": "", "CategoryId": [], "countryId": 2, "cityId": []}
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://careers.topmatch.co.il",
    "Referer": "https://careers.topmatch.co.il/biu/",
}
COLUMNS = [
    "title", "city", "url", "date", "deadline",
    "department", "description", "requirements",
]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")


def strip_html(raw):
    """Turn the RedMatch description HTML into readable plain text."""
    if not raw:
        return ""
    text = raw.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"</(p|li|ul|h1|h2|h3|div)>", "\n", text, flags=re.I)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    # collapse whitespace, keep line breaks
    lines = [WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def iso_date(s):
    """RedMatch dates look like 2026-06-02T10:42:14.217 -> 2026-06-02."""
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
        print(f"   x could not fetch BIU positions: {e}")
        return None


def parse(data):
    jobs = []
    for p in (data or {}).get("positions", []) or []:
        if not p.get("isActivePosition", True):
            continue
        pid = p.get("compPositionID")
        title = (p.get("jobTitleText") or "").strip()
        # Some titles are wrapped in ** markers in the source data
        title = title.strip("*").strip()
        if not title or pid is None:
            continue
        # Expiration date 0001-01-01 means "no deadline set"
        deadline = iso_date(p.get("scheduleExpirationDate"))
        if deadline.startswith("0001"):
            deadline = ""
        jobs.append({
            "title": title,
            "city": (p.get("displayLocation") or "רמת גן").strip(),
            "url": POSITION_URL.format(id=pid),
            "date": iso_date(p.get("activationDate")) or TODAY,
            "deadline": deadline,
            "department": (p.get("fieldDesc") or "").strip(),
            "description": strip_html(p.get("description")),
            "requirements": "",
        })
    return jobs


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_bar():
    print("\n-- Bar-Ilan University (BIU) ---------------------------------------")
    data = fetch()
    jobs = parse(data)
    write_csv(jobs, f"bar_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_bar()
    print(f"\nDone. {count} Bar-Ilan jobs.")
    sys.exit(0)
