#!/usr/bin/env python3
"""
fetch_harel.py — Scrapes open positions at Harel Insurance (הראל).

  Site:   harel-group.co.il/careers → AdamTOTAL ATS
  URL:    career.adamtotal.co.il/?token=6675d401-0dee-428a-a776-5d41885d16b0-harel
  Tech:   Server-rendered HTML (ASP.NET MVC). Paginated (?page=N), 25 jobs/page.
          Each article has data-job-title, data-job-id, .job-meta spans, .description-text.
          Pages are large (~23 MB each due to embedded base64 logos) — lxml parser used.
  WAF:    None.
  Dedup:  by URL (per-job token URL in /Jobs/JobDetails?token=...).
  LOCAL-ONLY (run via run_fetch.bat).

Output: harel_jobs_YYYY-MM-DD.csv
Usage:  py fetch_harel.py
"""

import csv, glob, re, sys
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"harel_jobs_{TODAY}.csv"
SOURCE      = "harel"
COMPANY     = "הראל"
BASE_URL    = "https://career.adamtotal.co.il"
TOKEN       = "6675d401-0dee-428a-a776-5d41885d16b0-harel"
LIST_URL    = f"{BASE_URL}/?token={TOKEN}"
PAGE_URL    = f"{BASE_URL}/Home/Index?page={{page}}&token={TOKEN}"

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "he-IL,he;q=0.9",
}


def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה|זמני', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"חצי משרה|משרה חלקית|חלקית|חלקי|סטודנט", t):
        return "part_time"
    return ""


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("harel_jobs_*.csv"))
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


def parse_page(html_bytes):
    soup = BeautifulSoup(html_bytes, "lxml")
    # Remove embedded images (base64 bloat in each article)
    for img in soup.find_all("img"):
        img.decompose()
    return soup.find_all("article", class_="job-card")


def scrape():
    first_seen = load_first_seen()
    session = requests.Session()
    session.headers.update(HEADERS)

    all_jobs = []
    seen_urls = set()

    page_num = 1
    while True:
        url = LIST_URL if page_num == 1 else PAGE_URL.format(page=page_num)
        print(f"  Page {page_num}: {url[:70]} ...")
        r = session.get(url, timeout=60)
        if r.status_code != 200:
            print(f"  → {r.status_code}, stopping")
            break

        articles = parse_page(r.content)
        if not articles:
            print(f"  → 0 articles, done")
            break

        print(f"  → {len(articles)} articles")

        for art in articles:
            title = (art.get("data-job-title") or "").strip()
            if not title:
                continue

            # Per-job URL
            a_tag = art.find("a", href=True)
            href = a_tag["href"] if a_tag else ""
            job_url = BASE_URL + href if href.startswith("/") else href

            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            # Department and location from .job-meta span children
            meta = art.find(class_="job-meta")
            meta_items = []
            if meta:
                for child in meta.find_all(True):
                    txt = child.get_text(" ", strip=True)
                    if txt and txt not in meta_items:
                        meta_items.append(txt)
                # meta_items[0] = "מס' משרה: XXXX", [1] = dept, [2] = location
                # Remove job number string from list
                meta_items = [x for x in meta_items if "מס' משרה" not in x]

            department = meta_items[0].strip() if len(meta_items) >= 1 else ""
            location   = meta_items[1].strip() if len(meta_items) >= 2 else ""
            # Clean up location: "גוש דן | בית הראל רמת גן" → "רמת גן" / "גוש דן"
            if "|" in location:
                # Take what's after the last pipe
                parts = [p.strip() for p in location.split("|") if p.strip()]
                location = parts[-1] if parts else location

            # Description from .description-text
            desc_el = art.find(class_="description-text")
            description = ""
            if desc_el:
                description = re.sub(r"\s+", " ", desc_el.get_text(" ", strip=True))[:1500]

            pt = title_to_position_type(title)

            all_jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       location or "רמת גן",
                "date":           first_seen.get(job_url, TODAY),
                "url":            job_url,
                "department":     department,
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    description,
                "position_type":  pt,
            })
            tag = f" [{pt}]" if pt else ""
            print(f"    {title[:55]}{tag}")

        page_num += 1
        if page_num > 10:  # safety cap
            break

    return all_jobs


def main():
    print(f"[Harel] scraping {LIST_URL} ...")
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
