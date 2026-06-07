#!/usr/bin/env python3
"""
fetch_szmc.py — Shaare Zedek Medical Center (שערי צדק) open positions scraper.

Source: HunterHRMS portal at https://szmc.hunterhrms.com
The listing is JS-rendered, so we drive it with Playwright (headless Chromium),
click through each job category to reveal all jobs, collect their job-codes, then
fetch each job-detail page for description/requirements.

Output: szmc_jobs_{TODAY}.csv with the columns the frontend's normSzmc() expects.

Requires: playwright (pip install playwright; playwright install chromium)
Runs locally (Israeli IP). HunterHRMS / .il sites often block datacenter IPs.
"""

import csv
import re
import sys
import time
from datetime import date, timedelta

from bs4 import BeautifulSoup

TODAY = date.today().isoformat()


def load_first_seen(pattern, key_field="url"):
    import glob
    from datetime import timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob(pattern))
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
        with open(prev_file, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = row.get(key_field, "").strip()
                d = row.get("date", "").strip()
                if k and d:
                    result[k] = d
    except Exception:
        pass
    return result

BASE_URL = "https://szmc.hunterhrms.com"
COMPANY = "שערי צדק"
LOCATION = "Jerusalem"
# Hebrew "פרטי-משרה" (job details) path, URL-encoded
DETAIL_BASE = BASE_URL + "/%d7%a4%d7%a8%d7%98%d7%99-%d7%9e%d7%a9%d7%a8%d7%94/"
CATEGORIES = [
    "אדמיניסטרציה", "לוגיסטיקה ותשתיות", "מחקר ופיתוח", "מחשוב",
    "מקצועות הבריאות", "סיעוד וכוחות עזר", "רפואה", "תחומים נוספים",
]
COLUMNS = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "description", "requirements",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


def pw_get(url, wait_ms=2000):
    """Fetch a page's rendered HTML using Playwright headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(wait_ms)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"   [pw error] {e}")
        return None


def collect_job_codes():
    """Open the portal, click through every category, gather {code: title}."""
    all_codes = {}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            page.goto(BASE_URL + "/", wait_until="networkidle", timeout=30000)
            time.sleep(2)

            def extract():
                soup = BeautifulSoup(page.content(), "html.parser")
                for el in soup.select("[job-code]"):
                    code = el.get("job-code", "").strip()
                    if not code or code in all_codes:
                        continue
                    te = el.select_one(".hot-job-name,.job-title,h5,label")
                    t = te.get_text(strip=True) if te else el.get_text(strip=True)
                    if t:
                        all_codes[code] = t
                for wrap in soup.select(".job-wrap"):
                    lbl = wrap.select_one("label.job-title")
                    if not lbl:
                        continue
                    c = lbl.get("for", "").strip()
                    if c and c not in all_codes:
                        all_codes[c] = lbl.get_text(strip=True)

            extract()
            for cat in CATEGORIES:
                try:
                    btn = page.locator(f"text={cat}").first
                    if btn.count():
                        btn.click()
                        time.sleep(1.5)
                        extract()
                except Exception:
                    pass
            browser.close()
    except Exception as e:
        print(f"   x Playwright error: {e}")
    return all_codes


def fetch_description(jobcode):
    url = f"{DETAIL_BASE}?jobcode={jobcode}"
    html = pw_get(url, wait_ms=2000)
    if not html:
        return "", "", url
    soup = BeautifulSoup(html, "html.parser")
    full = soup.get_text("\n", strip=True)
    desc, reqs = "", ""
    for m in ["תיאור המשרה", "תיאור התפקיד:", "תיאור התפקיד"]:
        if m in full:
            after = full.split(m, 1)[1]
            for s in ["דרישות המשרה", "דרישות התפקיד:", "הערות", "כפיפות:"]:
                if s in after:
                    after = after.split(s, 1)[0]
            desc = after.strip()[:2000]
            break
    for m in ["דרישות המשרה", "דרישות התפקיד:"]:
        if m in full:
            after = full.split(m, 1)[1]
            for s in ["הערות", "כפיפות:", "היקף משרה:"]:
                if s in after:
                    after = after.split(s, 1)[0]
            reqs = after.strip()[:2000]
            break
    return desc, reqs, url


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_szmc():
    print("\n-- Shaare Zedek Medical Center (שערי צדק) ---------------------------")
    first_seen = load_first_seen("szmc_jobs_*.csv", key_field="url")
    all_codes = collect_job_codes()
    if not all_codes:
        print("   x No jobs found")
        write_csv([], f"szmc_jobs_{TODAY}.csv")
        return 0
    items = list(all_codes.items())
    print(f"   Found {len(items)} jobs — fetching descriptions...")
    jobs = []
    for i, (code, title) in enumerate(items, 1):
        desc, reqs, url = fetch_description(code)
        jobs.append({
            "title": re.sub(r"\s+", " ", title).strip(),
            "company": COMPANY,
            "location": LOCATION,
            "date": first_seen.get(url, TODAY),
            "url": url,
            "department": "",
            "workplace_type": "onsite",
            "description": desc,
            "requirements": reqs,
        })
        print(f"   [{i}/{len(items)}] {title[:60]}")
        time.sleep(0.3)
    write_csv(jobs, f"szmc_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_szmc()
    print(f"\nDone. {count} Shaare Zedek jobs.")
    sys.exit(0)
