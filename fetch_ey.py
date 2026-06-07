#!/usr/bin/env python3
"""
fetch_ey.py — EY Israel (ארנסט אנד יאנג) open positions scraper.

Source: https://ey.co.il/career/  (JS-rendered → Playwright)
Job links point to https://ey.co.il/open-jobs/{N}/. Each detail page has the title,
city, department, work type, description, and requirements (Hebrew section markers).

Output: ey_jobs_{TODAY}.csv (columns: title, company, city, date, url,
department, workplace_type, description, requirements).

Requires Playwright. Runs locally.
"""

import csv
import sys
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

CAREER_URL = "https://ey.co.il/career/"
BASE = "https://ey.co.il"
COMPANY = "EY Israel"
COLUMNS = [
    "title", "company", "city", "date", "url",
    "department", "workplace_type", "description", "requirements",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


def pw_get(url, wait_selector=None, wait_ms=2500):
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


def run_ey():
    print("\n-- EY Israel ---------------------------------------------------------")
    first_seen = load_first_seen("ey_jobs_*.csv", key_field="url")
    html = pw_get(CAREER_URL, wait_selector="a[href*='/open-jobs/']")
    if not html:
        print("   x could not fetch EY career page")
        write_csv([], f"ey_jobs_{TODAY}.csv")
        return 0

    soup = BeautifulSoup(html, "html.parser")
    job_urls = []
    seen_urls = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "/open-jobs/" not in href:
            continue
        url = href if href.startswith("http") else BASE + href
        if url in seen_urls:
            continue
        seen_urls.add(url)
        job_urls.append(url)

    print(f"   Found {len(job_urls)} job links — fetching details...")
    jobs = []
    seen_titles = set()
    for i, url in enumerate(job_urls, 1):
        detail_html = pw_get(url)
        if not detail_html:
            print(f"   [{i}] skip")
            continue
        d = BeautifulSoup(detail_html, "html.parser")
        h1 = d.select_one("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title:
            continue
        t_key = title.lower().strip()
        if t_key in seen_titles:
            continue
        seen_titles.add(t_key)
        full = d.get_text("\n", strip=True)
        city = "Tel Aviv"
        if "Haifa" in full or "חיפה" in full:
            city = "Haifa"
        dept = ""
        for el in d.select("ul li, .job-meta span"):
            t = el.get_text(strip=True)
            if t and t not in ["משרה מלאה", "תל-אביב", "חיפה", "משרה חלקית", "Full time"] and len(t) < 50:
                dept = t
                break
        worktype = "parttime" if "משרה חלקית" in full else "fulltime"
        desc, reqs = "", ""
        if "תיאור התפקיד" in full:
            after = full.split("תיאור התפקיד", 1)[1]
            for stop in ["מה נדרש", "דרישות", "להגשת מועמדות"]:
                if stop in after:
                    after = after.split(stop, 1)[0]
            desc = after.strip()
        if "מה נדרש" in full:
            after = full.split("מה נדרש", 1)[1]
            for stop in ["להגשת מועמדות", "הכירו את הצוות", "חזרה לעמוד"]:
                if stop in after:
                    after = after.split(stop, 1)[0]
            reqs = after.strip()
        jobs.append({
            "title": title, "company": COMPANY, "city": city,
            "date": first_seen.get(url, TODAY), "url": url, "department": dept,
            "workplace_type": worktype, "description": desc, "requirements": reqs,
        })
        print(f"   [{i}/{len(job_urls)}] {title[:60]}")

    write_csv(jobs, f"ey_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_ey()
    print(f"\nDone. {count} EY jobs.")
    sys.exit(0)
