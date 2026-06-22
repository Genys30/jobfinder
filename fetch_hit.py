#!/usr/bin/env python3
"""
fetch_hit.py — Scrapes open positions at HIT (Holon Institute of Technology,
מכון טכנולוגי חולון) from the institute's own "דרושים" page.

  Source: https://www.hit.ac.il/jobs/
  CMS:    WordPress, server-rendered. BUT the site sits behind a Sucuri/SPD
          gateway that 302-redirects plain requests to //abuse.spd.co.il in a
          loop (it sets ZNPCQ.../HITHTTPSSRVID cookies and expects a real
          browser TLS fingerprint). curl_cffi `chrome110` clears it on the
          first request — no Playwright needed (HTML is server-rendered).

  Jobs live in a Bootstrap accordion split across TWO tabs:
    div.tab-pane#tab_con_0  →  div.accordion#JOB_accordion0  →  admin (מנהליות)
    div.tab-pane#tab_con_1  →  div.accordion#JOB_accordion1  →  academic (אקדמיות)
  Each job: div.accordion-item
              div.accordion_title   ← title
              div.accordion-body    ← description (inline, rich → pop-up works)

  This is the institute's OWN open positions (employer-type: academic), NOT the
  Telem board (hit.ac.il/telem-jobs) which lists external employers.

No per-job URL (accordion toggles in-page, apply by email / embedded eforms),
so first_seen is keyed by TITLE — same approach as Afeka / Braude / BGU.

Output: hit_jobs_YYYY-MM-DD.csv
Usage:  py fetch_hit.py
"""

import csv, re, sys, glob, time
from datetime import date, timedelta

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("curl_cffi not installed. Run: pip install curl_cffi")
    sys.exit(1)

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"hit_jobs_{TODAY}.csv"
SOURCE      = "hit"
COMPANY     = "מכון טכנולוגי חולון (HIT)"
LOCATION    = "חולון"
PAGE_URL    = "https://www.hit.ac.il/jobs/"

# Accordion container id → department bucket.
TAB_DEPARTMENT = {
    "JOB_accordion0": "admin_staff",
    "JOB_accordion1": "academic_faculty",
}

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

# ── position_type detection (ONLY values the frontend Contract filter knows:
#    maternity_cover / part_time / freelance / internship; else '' → full_time).
#    postdoc / visiting / external-lecturer intentionally fall through to '' so
#    the badge shows Full-time rather than an unrecognized (blank) badge. ───────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|'
        r'מילוי מקום לחופשת לידה|ממלא.?ת? מקום|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|part.?time|part time',
        re.I | re.UNICODE
    ),
    'freelance': re.compile(
        r'פרילנס|פרי-לנס|freelance|free.?lance',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|מתמחה|\bintern\b|\binternship\b|\btrainee\b",
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
    t = re.sub(r'\s+', ' ', (t or '')).strip()
    # strip a leading boilerplate prefix the institute uses on most titles
    t = re.sub(r'^למכון טכנולוגי(?: חולון)?\s+', '', t)
    return t.strip()


def load_first_seen():
    """Read the most recent previous hit CSV → {url: date} dict. Each job's url
    carries a unique #collapseN fragment, so url is a stable per-job key even
    when two jobs share a title."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("hit_jobs_*.csv"))
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


def fetch_html():
    """curl_cffi with chrome110 TLS impersonation clears the Sucuri/SPD gateway.
    Warm up on the home page first (lets the gateway set its cookies on the
    session), then fetch /jobs/. Retries a few times on timeout/5xx."""
    session = cffi_requests.Session(impersonate="chrome110")
    # Warm-up: hit the home page so the gateway issues ZNPCQ/HITHTTPSSRVID cookies.
    try:
        session.get("https://www.hit.ac.il/", timeout=30)
        time.sleep(1.5)
    except Exception as e:
        print(f"  (warm-up skipped: {e})")

    last = None
    for attempt in range(1, 4):
        try:
            r = session.get(PAGE_URL, timeout=45)
            if r.status_code == 200 and r.text:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        print(f"  attempt {attempt}/3 failed: {last} — retrying…")
        time.sleep(2.5)
    print(f"  ✗ giving up after 3 attempts: {last}")
    return None


def scrape() -> list[dict]:
    print(f"\n[HIT] {PAGE_URL}")
    html = fetch_html()
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    for acc_id, dept in TAB_DEPARTMENT.items():
        acc = soup.find(id=acc_id)
        if not acc:
            print(f"  [{dept}] accordion #{acc_id} not found")
            continue
        items = acc.select("div.accordion-item")
        print(f"  [{dept}] {len(items)} accordion items")

        for item in items:
            title_el = item.select_one("div.accordion_title")
            if not title_el:
                continue
            title = clean_title(title_el.get_text(" ", strip=True))
            if not title:
                continue

            body_el = item.select_one("div.accordion-body")
            desc = body_el.get_text(" ", strip=True) if body_el else ""
            desc = re.sub(r'\s+', ' ', desc).strip()

            # Each accordion item has a unique, stable id (data-bs-target="#collapseN"
            # / <div id="collapseN">, post-id based). Use it as a URL fragment so
            # two distinct jobs that share a title (e.g. two "משרת פוסטדוק |
            # Postdoctoral Position" for different labs) stay separate.
            collapse = item.select_one(".accordion-collapse")
            cid = collapse.get("id") if collapse else None
            if not cid:
                btn = item.select_one("button[data-bs-target]")
                cid = (btn.get("data-bs-target") or "").lstrip("#") if btn else ""
            url = PAGE_URL + ("#" + cid if cid else "")

            if url in seen:
                continue
            seen.add(url)

            jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       LOCATION,
                "date":           first_seen.get(url, TODAY),
                "url":            url,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    desc[:1000],
                "position_type":  detect_position_type(title, desc),
            })

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
    for j in jobs[:15]:
        pt = f" [{j['position_type']}]" if j['position_type'] else ""
        print(f"  • [{j['department'][:6]}] {j['title'][:50]}{pt}  ({len(j['description'])} chars)")

    print("\nNext steps:")
    print("  git add -f hit_jobs_*.csv")
    print("  git add fetch_hit.py run_fetch.bat")
    print("  git commit -m 'feat: add HIT college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
