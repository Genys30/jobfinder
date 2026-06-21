#!/usr/bin/env python3
"""
fetch_sce.py — Scrapes open positions at SCE (Sami Shamoon College of
Engineering / המכללה האקדמית להנדסה ע"ש סמי שמעון) from the college's own
HR "wanted" pages.

  Hub:   https://www.sce.ac.il/administration/human-resources1/wanted
  Jobs live on THREE server-rendered sub-pages (admin / academic / research).
  Admin jobs link to the external CIVI ATS (app.civi.co.il/promo/id=NNNNNN);
  academic & research jobs link to internal SCE detail pages under the sub-page
  (e.g. /wanted/academic/physics).
  The HTML is server-rendered, BUT sce.ac.il sits behind a WAF JS-challenge:
  plain requests AND curl_cffi TLS impersonation both get 403 (the challenge
  cookie is set by executing JS, which neither can do). So we use Playwright —
  a real browser solves the challenge automatically. The page content itself
  needs no JS rendering or clicking; we just read the DOM after the challenge
  clears. ONE shared browser context warms up on the hub (solving the challenge
  once), then visits the three sub-pages reusing the cookie.

  This is the college's OWN open positions (employer-type: academic), NOT the
  student/alumni job board (secure.wanted.co.il), which lists external employers.

NOTE: .il sites often block cloud/CI IPs (403). Run this LOCALLY via
      run_fetch.bat and commit the CSV manually.

Each job HAS a unique per-job URL (the CIVI `id`), so first_seen + dedup are
keyed by the **normalized URL** (the `&src=` tracking param is stripped — it
varies between runs and would otherwise break dedup).

v1: titles + apply URLs only. Descriptions live on the CIVI detail pages and
    are NOT fetched here (like Deloitte). Can be added later as v2.

Output: sce_jobs_YYYY-MM-DD.csv
Usage:  py fetch_sce.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

from bs4 import BeautifulSoup

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"sce_jobs_{TODAY}.csv"
SOURCE      = "sce"
COMPANY     = "מכללת סמי שמעון (SCE)"

# The three HR "wanted" sub-pages, each mapped to a department bucket.
PAGES = {
    "https://www.sce.ac.il/administration/human-resources1/wanted/administration":     "admin_staff",
    "https://www.sce.ac.il/administration/human-resources1/wanted/academic":           "academic_faculty",
    "https://www.sce.ac.il/administration/human-resources1/wanted/post-doc-researches": "research",
}

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

# ── position_type detection (same patterns as bgu / maccabi / afeka) ──────────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|מילוי מקום לחופשת לידה|'
        r'ממלא.?ת? מקום|maternity.?cover|maternity.?leave.?cover|covering.?maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|part.?time|part time',
        re.I | re.UNICODE
    ),
    'temporary': re.compile(
        r'זמני|תקופה זמנית|לתקופה קצובה|temporary|temp\b',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|התמחות|מתמחה|intern(ship)?|trainee",
        re.I | re.UNICODE
    ),
}

def detect_position_type(title='', description=''):
    text = (title + ' ' + description).strip()
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(text):
            return pt
    return ''


def clean_title(t):
    """Normalize whitespace and collapse the doubled link labels the site emits.
    Handles three shapes:
      'ABC ABC'            -> 'ABC'   (exact word doubling)
      'ABC ABC | sitename' -> 'ABC'   (link title attr appends the site name)
      'ABC DEF ABC | ...'  -> 'ABC'   (visible label + title attr differ)
    """
    t = re.sub(r'\s+', ' ', (t or '')).strip()
    # 1) Drop a trailing "| ..." suffix (the link's title attr appends site name).
    if '|' in t:
        t = t.split('|')[0].strip()
    words = t.split(' ')
    n = len(words)
    # 2) Smallest repeated word-prefix: words[:k] == words[k:2k] -> keep words[:k].
    for k in range(1, n // 2 + 1):
        if words[:k] == words[k:2 * k]:
            return ' '.join(words[:k])
    # 3) Fallback: exact first-half == second-half (even word count).
    if n >= 2 and n % 2 == 0 and words[:n // 2] == words[n // 2:]:
        return ' '.join(words[:n // 2])
    return t


def normalize_url(href):
    """Canonical, stable URL for first_seen/dedup. CIVI promo links keep only
    the numeric id (drop &src=); internal SCE detail pages are made absolute and
    stripped of any query/fragment."""
    href = (href or "").strip()
    m = re.search(r'/promo/id=(\d+)', href)
    if m:
        return f"https://app.civi.co.il/promo/id={m.group(1)}"
    href = href.split('#')[0].split('?')[0].rstrip('/')
    if href.startswith('/'):
        href = "https://www.sce.ac.il" + href
    return href


def detect_city(title):
    return "אשדוד" if "אשדוד" in title else "באר שבע"


def load_first_seen():
    """Read the most recent previous sce CSV → {url: date} dict.
    SCE jobs have real per-job CIVI URLs, so first_seen is keyed by URL."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("sce_jobs_*.csv"))
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
        with open(prev_file, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                u = row.get('url', '').strip()
                d = row.get('date', '').strip()
                if u and d:
                    result[u] = d
    except Exception:
        pass
    return result


HUB_URL      = "https://www.sce.ac.il/administration/human-resources1/wanted"
JOB_LINK_SEL = 'a[href*="civi.co.il/promo/id="]'


def fetch_html(page, url):
    """Load a sub-page in the shared browser context and return its HTML once
    the CIVI job links have rendered (WAF challenge already cleared on warm-up)."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print(f"  ✗ load error: {e}")
        return None
    try:
        page.wait_for_selector(JOB_LINK_SEL, timeout=15000)
    except Exception:
        page.wait_for_timeout(4000)  # no links yet (maybe none open) — brief wait
    return page.content()


def scrape() -> list[dict]:
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(user_agent=HEADERS["User-Agent"], locale="he-IL")
    page = context.new_page()

    # Warm up on the hub so the WAF JS-challenge resolves once; the cookie is
    # then reused for all three sub-pages via the shared browser context.
    try:
        page.goto(HUB_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"  [warm-up warning] {e}")

    for page_url, dept in PAGES.items():
        print(f"\n[SCE {dept}] {page_url}")
        html = fetch_html(page, page_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        # Two job-link shapes on SCE:
        #   • admin → external CIVI ATS  (app.civi.co.il/promo/id=NNNNNN)
        #   • academic / research → internal detail pages *under this sub-page*
        #     (e.g. /wanted/academic/physics). Sibling/nav links like
        #     /wanted/academic (no trailing slug) are NOT matched.
        base_path = page_url.split("sce.ac.il")[-1].rstrip("/")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if re.search(r'/promo/id=\d+', href) or (base_path + "/") in href:
                links.append(a)
        print(f"  Found {len(links)} job links")

        for a in links:
            href = a.get("href", "")
            url = normalize_url(href)
            if not url:
                continue
            title = clean_title(a.get_text(" ", strip=True))
            if not title:
                continue

            if url in seen:
                continue
            seen.add(url)

            jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       detect_city(title),
                "date":           first_seen.get(url, TODAY),
                "url":            url,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    "",
                "position_type":  detect_position_type(title),
            })

    browser.close()
    pw.stop()

    print(f"\n  → {len(jobs)} jobs total")
    return jobs


def main():
    jobs = scrape()

    # 0-row guard: skip CSV write so health check falls back to yesterday's file.
    if not jobs:
        print("\n⚠️  No jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\n✅ Wrote {len(jobs)} jobs → {OUTPUT_FILE}")
    print("\nSample:")
    for j in jobs[:12]:
        tail = j['url'].split('id=')[-1] if 'id=' in j['url'] else j['url'].rsplit('/', 1)[-1]
        print(f"  • [{j['department']}] {j['title'][:50]}  ({tail})")

    print("\nNext steps:")
    print("  git add -f sce_jobs_*.csv")
    print("  git add fetch_sce.py run_fetch.bat")
    print("  git commit -m 'feat: add SCE college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
