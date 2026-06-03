#!/usr/bin/env python3
"""
fetch_deloitte.py — Deloitte Israel open positions scraper.

Source: https://careers.deloitte.co.il/positions/  (WordPress, redesigned 2026)
Positions render as div.position-row inside div.positions-continer. The list shows
7 at a time and loads the rest via an AJAX "Load More" button
(a.positions-paginate-load-button). We use Playwright to click that exact button
until the row count stops growing, then parse all rows.

Each row:
  .position-row-title                      -> title
  .position-location (text after icon)     -> "{City}, Israel"
  .position-interest (text after icon)     -> area of interest (department)
  .position-row-link a[href]               -> /position/{id}-en/

Output: deloitte_jobs_{TODAY}.csv (columns: title, company, city, date, url,
department, workplace_type). Requires Playwright. Runs locally.
"""

import csv
import re
import sys
from datetime import date

from bs4 import BeautifulSoup

TODAY = date.today().isoformat()
URL = "https://careers.deloitte.co.il/positions/"
COMPANY = "Deloitte Israel"
COLUMNS = ["title", "company", "city", "date", "url", "department", "workplace_type"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")
CITY_MAP = {
    "Tel Aviv": "Tel Aviv", "Haifa": "Haifa", "Jerusalem": "Jerusalem",
    "Yokne'am Illit": "Yokneam Illit", "Yokneam Illit": "Yokneam Illit",
    "Beer Sheva": "Beer Sheva",
}


def get_full_html():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            def rows():
                return page.locator("div.position-row").count()

            for i in range(40):
                prev = rows()
                btn = page.locator("a.positions-paginate-load-button")
                if not btn.count() or not btn.first.is_visible():
                    break
                try:
                    btn.first.scroll_into_view_if_needed(timeout=3000)
                    page.wait_for_timeout(300)
                    try:
                        btn.first.click(timeout=3000)
                    except Exception:
                        btn.first.evaluate("el => el.click()")
                except Exception:
                    break
                page.wait_for_timeout(1500)
                now = rows()
                print(f"   load-more {i+1}: {prev} -> {now}")
                if now <= prev:
                    break

            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"   [pw error] {e}")
        return None


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_deloitte():
    print("\n-- Deloitte Israel ---------------------------------------------------")
    html = get_full_html()
    if not html:
        print("   x could not fetch Deloitte positions")
        write_csv([], f"deloitte_jobs_{TODAY}.csv")
        return 0

    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()
    for row in soup.select("div.position-row"):
        title_el = row.select_one(".position-row-title")
        title = clean(title_el.get_text()) if title_el else ""
        if not title:
            continue
        loc_el = row.select_one(".position-location")
        city = "Tel Aviv"
        if loc_el:
            m = re.match(r"^(.+?),\s*Israel$", clean(loc_el.get_text()))
            if m:
                city = CITY_MAP.get(m.group(1).strip(), m.group(1).strip())
        int_el = row.select_one(".position-interest")
        dept = clean(int_el.get_text()) if int_el else ""
        link = row.select_one(".position-row-link a[href]")
        url = link["href"] if link else URL
        if url in seen:
            continue
        seen.add(url)
        jobs.append({
            "title": title, "company": COMPANY, "city": city,
            "date": TODAY, "url": url, "department": dept, "workplace_type": "onsite",
        })

    write_csv(jobs, f"deloitte_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_deloitte()
    print(f"\nDone. {count} Deloitte jobs.")
    sys.exit(0)
