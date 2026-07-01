#!/usr/bin/env python3
"""
fetch_clal.py — Scrapes open positions at Clal Insurance (כלל ביטוח).

  Site:   clalbit.co.il/careers
  API:    clalbit.co.il/umbraco/surface/JobSearch/GetInitData?IsClal4UBool=false
  Tech:   Angular SPA. API requires browser session cookies; intercepted via
          Playwright response listener. Returns all 95 jobs in one call.
  WAF:    None (once browser session is established).
  Dedup:  by URL (fragment = JobId, e.g. /careers/#50060757).
  LOCAL-ONLY (run via run_fetch.bat).

Output: clal_jobs_YYYY-MM-DD.csv
Usage:  py fetch_clal.py
"""

import csv, glob, json, re, sys
from datetime import date, timedelta
from html.parser import HTMLParser

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"clal_jobs_{TODAY}.csv"
SOURCE      = "clal"
COMPANY     = "כלל ביטוח"
BASE_URL    = "https://www.clalbit.co.il"
LIST_URL    = BASE_URL + "/careers/"

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "he-IL,he;q=0.9",
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
    candidates = sorted(glob.glob("clal_jobs_*.csv"))
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
    captured = {}

    def on_response(resp):
        if "GetInitData" in resp.url and not captured:
            try:
                captured["body"] = resp.body()
            except Exception:
                pass

    print(f"[Clal] navigating to {LIST_URL} ...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="he-IL",
        )
        page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.goto(LIST_URL, timeout=40000, wait_until="networkidle")
        except PWTimeout:
            page.goto(LIST_URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        browser.close()

    if not captured.get("body"):
        print("  ERROR: API response not captured.")
        return []

    raw = json.loads(captured["body"].decode("utf-8-sig"))
    all_jobs = raw.get("Jobs", [])
    print(f"  API returned {len(all_jobs)} jobs")

    jobs = []
    for j in all_jobs:
        title = (j.get("JobTitle") or "").strip()
        if not title:
            continue
        job_id = j.get("JobId") or ""
        url = f"{BASE_URL}/careers/#{job_id}" if job_id else LIST_URL

        location = (j.get("Location") or "").strip()
        department = (j.get("FieldDesc") or "").strip()
        desc = strip_html((j.get("JobDesc") or "") + " " + (j.get("Qualifications") or ""))[:1500]
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
            "description":    desc,
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
