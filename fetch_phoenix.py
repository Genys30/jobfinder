#!/usr/bin/env python3
"""
fetch_phoenix.py — Scrapes open positions at Phoenix Insurance (הפניקס).

  Site:   fnx.co.il (Phoenix's Hebrew-brand domain; phoenix.co.il DNS is dead)
  URL:    https://www.fnx.co.il/career/open-positions
  Tech:   Nuxt 2 SPA — first 10 jobs are SSR; rest are JS-paginated.
          No public API found (backend at digital-content.fnx.co.il is
          Radware-protected). Playwright required for full pagination.
  WAF:    AWS WAF challenge.js loaded, but does not block non-headless
          Playwright in practice.
  Pages:  ~5 pages × 10 jobs (94 total as of 2026-07).
  Detail: each /career/open-positions/{id} fetched for full description.
  Dedup:  by URL (unique job ID in path).
  LOCAL-ONLY (run via run_fetch.bat).

Output: phoenix_jobs_YYYY-MM-DD.csv
Usage:  py fetch_phoenix.py
"""

import csv, re, sys, glob, time
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"phoenix_jobs_{TODAY}.csv"
SOURCE      = "phoenix"
COMPANY     = "הפניקס"
BASE_URL    = "https://www.fnx.co.il"
LIST_URL    = BASE_URL + "/career/open-positions"
CARD_SEL    = 'a[href^="/career/open-positions/"]'

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"חצי משרה|משרה חלקית|חלקית|חלקי", t):
        return "part_time"
    if re.search(r"סטודנט", t):
        return "part_time"
    return ""


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("phoenix_jobs_*.csv"))
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


def parse_cards(page):
    """Return list of {title, url, department, scope} from current page DOM."""
    cards = page.query_selector_all(CARD_SEL)
    jobs = []
    for card in cards:
        href = card.get_attribute("href") or ""
        if not re.search(r'/career/open-positions/\d+', href):
            continue
        job_url = BASE_URL + href if href.startswith("/") else href
        tds = card.query_selector_all("div.filters-td")
        title      = clean(tds[0].inner_text()) if len(tds) > 0 else ""
        department = clean(tds[1].inner_text()) if len(tds) > 1 else ""
        scope      = clean(tds[2].inner_text()) if len(tds) > 2 else ""
        if not title:
            continue
        jobs.append({"title": title, "url": job_url, "department": department, "scope": scope})
    return jobs


def fetch_detail(page, url):
    """Navigate to detail page; return (location, description)."""
    try:
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        location = ""
        desc = ""

        # Try to get description from the page body
        for sel in [
            "div.position-description", "div.job-description",
            "div.position-content", "main .content", "article",
            "div[class*='description']", "section.position",
        ]:
            el = page.query_selector(sel)
            if el:
                text = clean(el.inner_text())
                if len(text) > 80:
                    desc = text[:1500]
                    break

        # Look for location in structured data or visible meta
        loc_el = page.query_selector("span[class*='location'], div[class*='location'], p[class*='location']")
        if loc_el:
            location = clean(loc_el.inner_text())[:60]

        return location, desc
    except PWTimeout:
        return "", ""
    except Exception:
        return "", ""


def scrape():
    first_seen = load_first_seen()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="he-IL",
        )
        list_page = ctx.new_page()
        detail_page = ctx.new_page()

        print(f"\n[Phoenix Insurance] navigating to {LIST_URL} ...")
        try:
            list_page.goto(LIST_URL, timeout=30000, wait_until="networkidle")
        except PWTimeout:
            list_page.goto(LIST_URL, timeout=30000, wait_until="domcontentloaded")
        list_page.wait_for_timeout(1500)

        raw_jobs = []
        seen_urls = set()

        # Click through each numbered page button
        for attempt in range(1, 15):  # hard cap
            cards = parse_cards(list_page)
            new = [c for c in cards if c["url"] not in seen_urls]
            if not new and attempt > 1:
                print(f"  page {attempt}: no new cards — done")
                break
            for c in new:
                seen_urls.add(c["url"])
            raw_jobs.extend(new)
            print(f"  page {attempt}: {len(new)} new cards (total {len(raw_jobs)})")

            # Find "next" page button — try numbered pages or הבא arrow
            next_btn = None
            # Try clicking page number button (attempt+1)
            try:
                next_btn = list_page.query_selector(f'li.page-item a:has-text("{attempt + 1}")')
            except Exception:
                pass
            if not next_btn:
                try:
                    # Try "הבא" (next) button
                    btns = list_page.query_selector_all('li.page-item a')
                    for btn in btns:
                        txt = (btn.inner_text() or "").strip()
                        if "הבא" in txt or "next" in txt.lower() or txt == ">":
                            next_btn = btn
                            break
                except Exception:
                    pass

            if not next_btn:
                print(f"  no next button after page {attempt}")
                break

            try:
                next_btn.click()
                list_page.wait_for_timeout(1200)
            except Exception as e:
                print(f"  click failed: {e}")
                break

        browser.close()

    if not raw_jobs:
        print("  No jobs found.")
        return []

    print(f"\n  Got {len(raw_jobs)} jobs from listing. Fetching details ...")

    # Fetch detail pages with a plain requests session for speed
    import requests
    from bs4 import BeautifulSoup

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }
    session = requests.Session()

    jobs = []
    for i, j in enumerate(raw_jobs, 1):
        location, desc = "", ""
        try:
            r = session.get(j["url"], headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")

                # Location from subtitle: "מיקום המשרה: ראשון לציון משרה קבועה | ..."
                sub = soup.select_one(".subtitle")
                if sub:
                    sub_text = sub.get_text(" ", strip=True)
                    loc_match = re.search(r'מיקום המשרה[:\s]+([^|]+)', sub_text)
                    if loc_match:
                        location = loc_match.group(1).strip()
                        # Strip trailing employment type and date text
                        location = re.sub(r'\s*(משרה\s+\S+|חלקית|קבועה|זמנית|תאריך.+)$', '', location).strip()

                # Description from info-section (SSR metadata; full requirements are JS-rendered)
                info = soup.select_one(".info-section")
                if info:
                    # Remove the group-info nav label ("פרטים נוספים")
                    group = info.select_one(".group-info")
                    if group:
                        group.decompose()
                    desc = clean(info.get_text(" ", strip=True))[:1500]
        except Exception:
            pass

        pt = title_to_position_type(j["title"])
        jobs.append({
            "title":          j["title"],
            "company":        COMPANY,
            "location":       location or "רמת גן",
            "date":           first_seen.get(j["url"], TODAY),
            "url":            j["url"],
            "department":     j["department"],
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    desc,
            "position_type":  pt,
        })
        tag = f" [{pt}]" if pt else ""
        print(f"  [{i}/{len(raw_jobs)}] {j['title'][:55]}{tag}")
        time.sleep(0.25)

    return jobs


def main():
    jobs = scrape()

    if not jobs:
        print("\nNo jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\nWrote {len(jobs)} jobs -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
