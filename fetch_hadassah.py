#!/usr/bin/env python3
"""
fetch_hadassah.py — Hadassah Medical Center (הדסה) open positions scraper.

Source: https://he.hadassah.org.il/wanted/careers/  (custom Next.js site)
The careers list is JS-rendered, so we drive it with Playwright (headless Chromium).
Job links contain "position-"; we collect them, then fetch each for a description.

Output: hadassah_jobs_{TODAY}.csv with the columns the frontend's normHadassah() expects.

Requires: playwright (pip install playwright; playwright install chromium)
Runs locally (Israeli IP). .il sites often block datacenter IPs.
"""

import csv
import re
import sys
import time
from datetime import date

from bs4 import BeautifulSoup

TODAY = date.today().isoformat()
BASE = "https://he.hadassah.org.il"
CAREERS = BASE + "/wanted/careers/"
COMPANY = "הדסה"
LOCATION = "Jerusalem"
COLUMNS = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "description", "requirements",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


def pw_get(url, wait_selector=None, wait_ms=2000):
    """Fetch a page's rendered HTML using Playwright headless Chromium."""
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


def fetch_desc(url):
    detail = pw_get(url, wait_ms=2000)
    if not detail:
        return ""
    d = BeautifulSoup(detail, "html.parser")
    full = d.get_text("\n", strip=True)
    for m in ["תיאור התפקיד", "תיאור", "פרטי המשרה"]:
        if m in full:
            after = full.split(m, 1)[1]
            for stop in ["דרישות", "תנאים", "היקף משרה", "הגשת מועמדות"]:
                if stop in after:
                    after = after.split(stop, 1)[0]
            return after.strip()[:2000]
    return ""


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_hadassah():
    print("\n-- Hadassah Medical Center (הדסה) -----------------------------------")
    html = pw_get(CAREERS, wait_selector="a[href*='position-']", wait_ms=3000)
    if not html:
        print("   x could not fetch Hadassah careers page")
        write_csv([], f"hadassah_jobs_{TODAY}.csv")
        return 0

    soup = BeautifulSoup(html, "html.parser")
    job_links = {}
    for a in soup.select("a[href*='position-']"):
        href = a.get("href", "")
        url = href if href.startswith("http") else BASE + href
        ne = a.select_one(".generic-page-link_nameContainer__4yeQN")
        title = (ne.get_text(strip=True) if ne else a.get_text(strip=True)).strip()
        if title and url not in job_links:
            job_links[url] = title

    if not job_links:
        print("   x No job links found")
        write_csv([], f"hadassah_jobs_{TODAY}.csv")
        return 0

    print(f"   Found {len(job_links)} jobs — fetching descriptions...")
    jobs = []
    for i, (url, title) in enumerate(job_links.items(), 1):
        desc = fetch_desc(url)
        jobs.append({
            "title": re.sub(r"\s+", " ", title).strip(),
            "company": COMPANY,
            "location": LOCATION,
            "date": TODAY,
            "url": url,
            "department": "",
            "workplace_type": "onsite",
            "description": desc,
            "requirements": "",
        })
        print(f"   [{i}/{len(job_links)}] {title[:60]}")
        time.sleep(0.3)

    write_csv(jobs, f"hadassah_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_hadassah()
    print(f"\nDone. {count} Hadassah jobs.")
    sys.exit(0)
