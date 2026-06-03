#!/usr/bin/env python3
"""
fetch_joint.py — The Joint / JDC Israel (ג'וינט) jobs scraper.

Source: https://www.thejoint.org.il/en/career/  (JS-rendered → Playwright)
Job links contain "juid"; aria-label holds the title. Each detail page has the
description/requirements.

Output: joint_jobs_{TODAY}.csv (columns: title, company, city, date, deadline, url,
department, workplace_type, description, requirements).

Requires Playwright. Runs locally.
"""

import csv
import re
import sys
import time
from datetime import date

from bs4 import BeautifulSoup

TODAY = date.today().isoformat()
BASE = "https://www.thejoint.org.il"
LIST_URL = BASE + "/en/career/"
COMPANY = "The Joint (ג'וינט)"
COLUMNS = [
    "title", "company", "city", "date", "deadline", "url",
    "department", "workplace_type", "description", "requirements",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


def pw_get(url, wait_selector=None, wait_ms=2000):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=8000)
                except Exception:
                    pass
            page.wait_for_timeout(wait_ms)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"   [pw error] {e}")
        return None


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_joint():
    print("\n-- The Joint (ג'וינט) ------------------------------------------------")
    html = pw_get(LIST_URL, wait_selector="a[href*='juid']", wait_ms=3000)
    if not html:
        print("   x could not fetch Joint career page")
        write_csv([], f"joint_jobs_{TODAY}.csv")
        return 0

    soup = BeautifulSoup(html, "html.parser")
    job_links = []
    seen = set()
    for a in soup.select("a[href*='juid']"):
        href = a.get("href", "")
        url = href if href.startswith("http") else BASE + href
        if url in seen:
            continue
        seen.add(url)
        aria = a.get("aria-label", "")
        if "Read more about the position:" in aria:
            title = aria.split("Read more about the position:", 1)[1].strip()
        else:
            title = a.get_text(strip=True)
        if not title:
            continue
        full_text = a.get_text(" ", strip=True)
        pub_date = ""
        dm = re.search(r"(\d{2}/\d{2}/\d{4})", full_text)
        if dm:
            pp = dm.group(1).split("/")
            pub_date = f"{pp[2]}-{pp[1]}-{pp[0]}"
        job_links.append({"title": title, "url": url, "date": pub_date or TODAY})

    print(f"   Found {len(job_links)} listings — fetching descriptions...")
    jobs = []
    for i, job in enumerate(job_links, 1):
        detail_html = pw_get(job["url"])
        desc, reqs, city = "", "", "ישראל"
        if detail_html:
            d = BeautifulSoup(detail_html, "html.parser")
            full = d.get_text("\n", strip=True)
            for c in ["תל אביב", "ירושלים", "חיפה", "באר שבע", "רמת גן",
                      "Tel Aviv", "Jerusalem", "Haifa"]:
                if c in full:
                    city = c
                    break
            for marker in ["About the position", "תיאור התפקיד", "Job Description"]:
                if marker in full:
                    after = full.split(marker, 1)[1]
                    for stop in ["Requirements", "דרישות", "What we're looking for"]:
                        if stop in after:
                            after = after.split(stop, 1)[0]
                    desc = after.strip()
                    break
            for marker in ["Requirements", "דרישות התפקיד", "What we're looking for"]:
                if marker in full:
                    after = full.split(marker, 1)[1]
                    for stop in ["Apply", "הגש", "Send CV", "שלח"]:
                        if stop in after:
                            after = after.split(stop, 1)[0]
                    reqs = after.strip()
                    break
        jobs.append({
            "title": job["title"], "company": COMPANY, "city": city,
            "date": job["date"], "deadline": "", "url": job["url"],
            "department": "", "workplace_type": "onsite",
            "description": desc, "requirements": reqs,
        })
        print(f"   [{i}/{len(job_links)}] {job['title'][:60]}")
        time.sleep(0.3)

    write_csv(jobs, f"joint_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_joint()
    print(f"\nDone. {count} Joint jobs.")
    sys.exit(0)
