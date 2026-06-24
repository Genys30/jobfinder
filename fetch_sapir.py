#!/usr/bin/env python3
"""
fetch_sapir.py — Scrapes open positions at Sapir Academic College
(המכללה האקדמית ספיר, Sderot) from the college's own jobs page, which is
powered by the CIVI ATS.

  Source:  https://www.sapir.ac.il/hr/wanted  (redirects to the CIVI feed)
  CIVI feed: https://app.civi.co.il/promos/id=NLY65YEJTW&src=13586
  We scrape the CIVI feed directly with ?rows=100 to get all jobs on one page.

  Each job is a card:
    <div class="thumb-content" onclick="openPromo(event,<JOBID>,13586,1)">
      <div class="title">…</div>      ← title
      <div class="descr">…</div>      ← description (inline, rich → pop-up works)
      …<div class="action-button" onclick="openPromo(event,<JOBID>,13586,1)">
  The job id lives in the openPromo(...) onclick → per-job URL is
  https://app.civi.co.il/promo/id=<JOBID>&src=13586 (real per-job URL, like SCE).

  Mixed academic + admin (scope = both). department is inferred from the title
  (חבר סגל / מרצה / מנחה / רקטור / דיקן → academic; else admin).

curl_cffi is used (CIVI sometimes blocks plain requests); requests is tried
first with a curl_cffi fallback.

Output: sapir_jobs_YYYY-MM-DD.csv
Usage:  py fetch_sapir.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

from bs4 import BeautifulSoup
import requests
try:
    from curl_cffi import requests as cffi_requests
    HAVE_CFFI = True
except ImportError:
    HAVE_CFFI = False

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"sapir_jobs_{TODAY}.csv"
SOURCE      = "sapir"
COMPANY     = "המכללה האקדמית ספיר"
LOCATION    = "שדרות"
CIVI_COMPANY = "NLY65YEJTW"
CIVI_SRC     = "13586"
FEED_BASE   = f"https://app.civi.co.il/promos/id={CIVI_COMPANY}&src={CIVI_SRC}"
# CIVI paginates with &p=N (20 jobs/page); ?rows=N is ignored. We loop pages.

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

# academic vs admin by title keywords
ACADEMIC_RX = re.compile(
    r'חבר.?ת? סגל|סגל אקדמי|סגל בכיר|מרצה|מרצים|מנחה|רקטור|דיקן|פרופסור|חוקר',
    re.I | re.UNICODE
)

# ── position_type (ONLY frontend-known values; else '' → full_time) ───────────
POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפת חופשת לידה|'
        r'מילוי מקום לחופשת לידה|ממלא.?ת? מקום|maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|חצי משרה|\b50%\b|\b25%\b|\b60%\b|\b75%\b|part.?time',
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


def clean_text(t):
    return re.sub(r'\s+', ' ', (t or '')).strip()


def load_first_seen():
    """Read the most recent previous sapir CSV → {url: date} dict.
    CIVI per-job promo links are real per-job URLs → key by URL."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("sapir_jobs_*.csv"))
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


def fetch_html(url):
    """Try plain requests first, fall back to curl_cffi (chrome110)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200 and r.text and 'thumb-content' in r.text:
            return r.text
        print(f"  requests: status={r.status_code} len={len(r.text)} (no cards) — trying curl_cffi")
    except Exception as e:
        print(f"  requests error: {e} — trying curl_cffi")
    if HAVE_CFFI:
        try:
            rc = cffi_requests.get(url, impersonate="chrome110", timeout=30)
            if rc.status_code == 200 and rc.text:
                return rc.text
            print(f"  curl_cffi: status={rc.status_code} len={len(rc.text)}")
        except Exception as e:
            print(f"  curl_cffi error: {e}")
    return None


def scrape() -> list[dict]:
    print(f"\n[Sapir] {FEED_BASE}")
    first_seen = load_first_seen()
    jobs = []
    seen = set()

    MAX_PAGES = 10
    for page in range(1, MAX_PAGES + 1):
        url = f"{FEED_BASE}&p={page}"
        html = fetch_html(url)
        if not html:
            print(f"  page {page}: fetch failed — stopping")
            break
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.thumb-content")
        new_on_page = 0

        for card in cards:
            title_el = card.select_one(".title")
            if not title_el:
                continue
            title = clean_text(title_el.get_text(" ", strip=True))
            if not title:
                continue

            desc_el = card.select_one(".descr")
            desc = clean_text(desc_el.get_text(" ", strip=True)) if desc_el else ""

            # job id from openPromo(event,<ID>,13586,1) anywhere in the card
            m = re.search(r'openPromo\(event,\s*(\d+)\s*,', str(card))
            if not m:
                continue
            job_id = m.group(1)
            url_job = f"https://app.civi.co.il/promo/id={job_id}&src={CIVI_SRC}"
            if url_job in seen:
                continue
            seen.add(url_job)
            new_on_page += 1

            dept = "academic_faculty" if ACADEMIC_RX.search(title) else "admin_staff"

            jobs.append({
                "title":          title,
                "company":        COMPANY,
                "location":       LOCATION,
                "date":           first_seen.get(url_job, TODAY),
                "url":            url_job,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         SOURCE,
                "description":    desc[:1000],
                "position_type":  detect_position_type(title, desc),
            })

        print(f"  page {page}: {len(cards)} cards, {new_on_page} new")
        # stop when a page brings no new jobs (last page reached)
        if new_on_page == 0:
            break

    print(f"  → {len(jobs)} jobs total")
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
    print("  git add -f sapir_jobs_*.csv")
    print("  git add fetch_sapir.py run_fetch.bat")
    print("  git commit -m 'feat: add Sapir college jobs scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
