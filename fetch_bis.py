#!/usr/bin/env python3
"""
fetch_bis.py — BIS (אגודת סטודנטים בר-אילן / Bar-Ilan student union) jobs scraper.

Source: https://www.bis.org.il/jobs  (Wix site, JS-rendered → Playwright)
Job titles render as <p class="font_2 wixui-rich-text__text"> with the real text in
an inner <span class="wixui-rich-text__text">. font_7 paragraphs are subtitle/desc lines.

Output: bis_jobs_{TODAY}.csv (columns: title, company, city, url, date, deadline,
department, description, requirements).

Requires Playwright. Runs locally.
"""

import csv
import re
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

URL = "https://www.bis.org.il/jobs"
COMPANY = "BIS - אגודת סטודנטים בר-אילן"
CITY = "רמת גן"
COLUMNS = [
    "title", "company", "city", "url", "date", "deadline",
    "department", "workplace_type", "description", "requirements",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")
SKIP = re.compile(
    r"BIS|אגודה|קריירה|career@|צרו קשר|פייסבוק|אינסטגרם|©|תנאי|"
    r"משרות|Jobs|חפש|מסננים|תחום|מעוניינים", re.I)


def pw_get(url, wait_ms=4000):
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


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_bis():
    print("\n-- BIS - אגודת סטודנטים בר-אילן ------------------------------------")
    first_seen = load_first_seen("bis_jobs_*.csv", key_field="url")
    html = pw_get(URL)
    if not html:
        print("   x could not fetch BIS jobs page")
        write_csv([], f"bis_jobs_{TODAY}.csv")
        return 0

    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()

    title_paragraphs = soup.select("p.font_2.wixui-rich-text__text")
    if not title_paragraphs:
        title_paragraphs = soup.select('[data-testid="richTextElement"] p')

    for p in title_paragraphs:
        inner = p.select_one("span.wixui-rich-text__text")
        t = (inner.get_text(strip=True) if inner else p.get_text(strip=True))
        if not t or len(t) < 4 or len(t) > 150:
            continue
        if SKIP.search(t):
            continue
        if t in seen:
            continue
        seen.add(t)

        desc, reqs = "", ""
        container = p.find_parent(
            lambda tag: tag.has_attr("data-testid")
            and "inline-content" in tag.get("data-testid", ""))
        if container:
            desc_parts = [el.get_text(strip=True)
                          for el in container.select("p.font_7.wixui-rich-text__text")
                          if el.get_text(strip=True)]
            full = "\n".join(desc_parts)
            for req_marker in ["דרישות התפקיד", "דרישות:", "Requirements", "כישורים"]:
                if req_marker in full:
                    parts = full.split(req_marker, 1)
                    desc = parts[0].strip()
                    reqs = (req_marker + "\n" + parts[1]).strip()
                    break
            else:
                desc = full

        worktype = "parttime" if any(w in t + desc for w in ["חלקית", "שעתי", "משמרות"]) else "onsite"

        apply_url = URL
        if container:
            for a in container.select("a[href]"):
                href = a.get("href", "")
                if href.startswith("http") and "bis.org.il" not in href:
                    apply_url = href
                    break

        jobs.append({
            "title": t, "company": COMPANY, "city": CITY,
            "url": apply_url, "date": first_seen.get(apply_url, TODAY), "deadline": "",
            "department": "", "workplace_type": worktype,
            "description": desc, "requirements": reqs,
        })
        print(f"   {t[:70]}")

    write_csv(jobs, f"bis_jobs_{TODAY}.csv")
    return len(jobs)


if __name__ == "__main__":
    count = run_bis()
    print(f"\nDone. {count} BIS jobs.")
    sys.exit(0)
