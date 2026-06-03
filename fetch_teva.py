#!/usr/bin/env python3
"""
fetch_teva.py — scrape Teva Israel job listings from careers.teva
Pattern: company (not source) — same as Osem/Movement Group.
Runs locally only (careers.teva blocks non-IL IPs).
Output: teva_jobs_YYYY-MM-DD.csv
"""

import csv
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://careers.teva"
LISTING_URL = (
    BASE_URL
    + "/search/?searchby=location&locationsearch=Israel&q=&startrow={start}"
)
TODAY = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"teva_jobs_{TODAY}.csv"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
PAGE_SIZE = 25
DELAY = 0.8  # seconds between requests


def get_soup(url: str, session: requests.Session) -> BeautifulSoup:
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def clean_location(raw: str) -> str:
    """'Tel Aviv, Israel, 6944020' -> 'Tel Aviv'"""
    parts = [p.strip() for p in raw.split(",")]
    return parts[0] if parts else raw.strip()


def scrape_description(url: str, session: requests.Session) -> tuple[str, str]:
    """Return (description_html, date_str) from a job detail page."""
    try:
        soup = get_soup(url, session)
        # Description: span[itemprop="description"] > span.jobdescription
        desc_span = soup.find("span", itemprop="description")
        description = ""
        if desc_span:
            inner = desc_span.find("span", class_="jobdescription")
            if inner:
                description = str(inner)
            else:
                description = desc_span.get_text(" ", strip=True)

        # Date: span[data-careersite-propertyid="date"]
        date_span = soup.find("span", attrs={"data-careersite-propertyid": "date"})
        date_str = ""
        if date_span:
            raw_date = date_span.get_text(strip=True)
            # "May 13, 2026" -> "2026-05-13"
            try:
                date_str = datetime.strptime(raw_date, "%B %d, %Y").strftime("%Y-%m-%d")
            except ValueError:
                date_str = raw_date

        return description, date_str
    except Exception as e:
        print(f"    WARNING: could not fetch detail {url}: {e}")
        return "", ""


def scrape_listing_page(start: int, session: requests.Session) -> list[dict]:
    url = LISTING_URL.format(start=start)
    print(f"  Fetching listing page startrow={start} ...")
    soup = get_soup(url, session)

    rows = soup.select("tr.data-row")
    if not rows:
        return []

    jobs = []
    for row in rows:
        # Title + URL
        link = row.select_one("a.jobTitle-link")
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link.get("href", "")
        job_url = BASE_URL + href if href.startswith("/") else href

        # Location
        loc_span = row.select_one("span.jobLocation")
        raw_loc = loc_span.get_text(strip=True) if loc_span else ""
        location = clean_location(raw_loc)

        # Department (jobFacility column)
        fac_span = row.select_one("span.jobFacility")
        department = fac_span.get_text(strip=True) if fac_span else ""

        jobs.append(
            {
                "title": title,
                "company": "Teva",
                "location": location,
                "date": "",  # filled from detail page
                "url": job_url,
                "department": department,
                "description": "",  # filled from detail page
            }
        )

    return jobs


def get_total_count(session: requests.Session) -> int:
    soup = get_soup(LISTING_URL.format(start=0), session)
    label = soup.select_one("span.paginationLabel")
    if label:
        text = label.get_text()
        m = re.search(r"of\s+(\d+)", text)
        if m:
            return int(m.group(1))
    return 0


def main():
    print(f"[fetch_teva] Starting — output: {OUT_FILE}")
    session = requests.Session()

    total = get_total_count(session)
    if total == 0:
        print("  WARNING: could not determine total count, will scrape until empty.")
        total = 999
    else:
        print(f"  Total jobs found: {total}")

    all_jobs = []
    start = 0
    while start < total:
        page_jobs = scrape_listing_page(start, session)
        if not page_jobs:
            break
        all_jobs.extend(page_jobs)
        start += PAGE_SIZE
        time.sleep(DELAY)

    print(f"  Collected {len(all_jobs)} jobs from listing pages.")
    print("  Fetching detail pages for descriptions and dates...")

    for i, job in enumerate(all_jobs, 1):
        print(f"  [{i}/{len(all_jobs)}] {job['title'][:60]}")
        desc, date_str = scrape_description(job["url"], session)
        job["description"] = desc
        job["date"] = date_str or TODAY
        time.sleep(DELAY)

    # Write CSV
    fieldnames = ["title", "company", "location", "date", "url", "department", "description"]
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_jobs)

    print(f"[fetch_teva] Done — wrote {len(all_jobs)} jobs to {OUT_FILE}")


if __name__ == "__main__":
    main()
