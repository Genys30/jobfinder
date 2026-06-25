#!/usr/bin/env python3
"""fetch_ruppin.py — Ruppin Academic Center's own open positions.

Source key: ruppin | employer-type: academic | output: ruppin_jobs_YYYY-MM-DD.csv

Ruppin sits behind an Imperva WAF (plain requests / curl_cffi -> status 247);
only a NON-headless real browser passes the challenge, so this uses Playwright
with headless=False. LOCAL-ONLY (cannot run in GitHub Actions CI).

Two listing pages, department by page (Tel-Hai pattern):
  academic -> academic_faculty   apply by email, no per-job URL
  admin    -> admin_staff        apply via a per-job PDF (מכרז) link

Keys (mixed, but frontend dedups uniformly by title+url):
  academic -> first_seen by clean TITLE, url = the page URL
  admin    -> first_seen by URL (the PDF link)

Selectors are the ones proven by the recon probe:
  div.card -> .card-header (title) + .card-body (body)
  requirements: <ul> after a requirements-marker <h4>
  apply email: a[href^="mailto:"] / email regex
  apply link (admin): non-mailto <a> whose text matches a submit-marker
"""
import re
import csv
import sys
import datetime
import pathlib
from glob import glob
from contextlib import contextmanager
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

PAGES = {
    "academic": ("https://www.ruppin.ac.il/administration/academic-staff-required/",
                 "academic_faculty"),
    "admin":    ("https://www.ruppin.ac.il/administration/administrative-staff-required/",
                 "admin_staff"),
}

COMPANY = "Ruppin Academic Center"
CITY = "Emek Hefer"
TODAY = datetime.date.today().isoformat()
OUT = f"ruppin_jobs_{TODAY}.csv"
FIELDS = ["title", "company", "department", "city", "url",
          "description", "position_type", "date"]

SUBMIT_MARKERS = ["להגשת מועמדות", "לפרטים המלאים", "לחצו כאן", "יש לשלוח", "על כל מועמד"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# zero-width + bidi marks that pollute Hebrew titles (academic is keyed by title!)
INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]")
INTERNAL_MARKER = "פנימית"  # internal-only postings — skipped (Anna's choice). No-op now.


def clean_title(s):
    """Strip invisible/bidi marks and collapse whitespace.
    Critical: academic rows are keyed by title, so an invisible char drifting
    between runs would otherwise make the same job look 'new' every day."""
    s = INVISIBLE_RE.sub("", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def position_type_of(title):
    """Only emit values the Contract filter knows. חל\"ד => maternity_cover, else ''."""
    heb_only = re.sub(r"[^\u0590-\u05FF]", "", title)  # drop quotes/spaces for the check
    return "maternity_cover" if "חלד" in heb_only else ""


def is_internal(card_text):
    return INTERNAL_MARKER in (card_text or "")


# ---- fetch -----------------------------------------------------------------
@contextmanager
def browser_fetch():
    """One non-headless browser for the whole run; get(url) -> html."""
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=False,                # REQUIRED — Imperva 247 blocks headless
            channel="chrome",              # remove if Chrome isn't installed (uses chromium)
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = b.new_context(
            locale="he-IL",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
        )

        def get(url):
            pg = ctx.new_page()
            pg.goto(url, wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(2000)
            html = pg.content()
            pg.close()
            return html

        try:
            yield get
        finally:
            b.close()


def looks_blocked(html):
    return len(html) < 5000 or ("Incapsula" in html and "incident" in html.lower())


# ---- parse -----------------------------------------------------------------
def parse_card(card, page_url, department):
    header = card.select_one(".card-header")
    body = card.select_one(".card-body")
    if not body:
        return None

    title = clean_title(header.get_text(" ", strip=True) if header else "")
    body_text = body.get_text("\n", strip=True)

    mailtos = [a["href"].replace("mailto:", "").split("?")[0]
               for a in body.select('a[href^="mailto:"]')]
    emails = sorted(set(mailtos + EMAIL_RE.findall(body.get_text(" ", strip=True))))

    apply_links = []
    for a in body.select("a[href]"):
        href = a.get("href") or ""
        if href.startswith("mailto:"):
            continue
        if any(m in a.get_text(" ", strip=True) for m in SUBMIT_MARKERS):
            apply_links.append(urljoin(page_url, href))
    apply_links = sorted(set(apply_links))

    h4s = [h.get_text(" ", strip=True) for h in body.select("h4")]
    # skip nav / non-job cards (recon guard)
    if not (h4s or emails or apply_links):
        return None
    if not title:
        return None
    if is_internal(body_text) or is_internal(title):
        return "INTERNAL"

    if apply_links:                       # admin: real per-job PDF link, no inline desc
        url = apply_links[0]
        description = ""
    else:                                 # academic: page URL, inline description
        url = page_url
        description = body_text

    return {
        "title": title,
        "company": COMPANY,
        "department": department,
        "city": CITY,
        "url": url,
        "description": description,
        "position_type": position_type_of(title),
    }


def parse_listing(html, page_url, department):
    soup = BeautifulSoup(html, "html.parser")
    jobs, internal = [], 0
    for card in soup.select("div.card"):
        v = parse_card(card, page_url, department)
        if v == "INTERNAL":
            internal += 1
        elif v:
            jobs.append(v)
    return jobs, internal


# ---- first_seen ------------------------------------------------------------
def row_key(row):
    """admin -> url, academic -> title (must match the keying on write)."""
    if row.get("department") == "admin_staff":
        return ("url", row.get("url", ""))
    return ("title", clean_title(row.get("title", "")))


def load_first_seen():
    """Read the most recent previous ruppin CSV (not today's) -> {key: date}."""
    prev = sorted(f for f in glob("ruppin_jobs_*.csv") if TODAY not in f)
    if not prev:
        return {}
    seen = {}
    try:
        with open(prev[-1], encoding="utf-8") as f:
            for row in csv.DictReader(f):
                d = row.get("date")
                if d:
                    seen[row_key(row)] = d
    except Exception as e:
        print(f"[first_seen] could not read {prev[-1]}: {e}")
    return seen


# ---- main ------------------------------------------------------------------
def main():
    all_jobs, internal_total = [], 0
    with browser_fetch() as get:
        for label, (url, department) in PAGES.items():
            html = get(url)
            if looks_blocked(html):
                print(f"[{label}] !!! Imperva block page — got {len(html)} bytes, skipping")
                continue
            jobs, internal = parse_listing(html, url, department)
            internal_total += internal
            all_jobs.extend(jobs)
            print(f"[{label}] {len(jobs)} jobs"
                  + (f" ({internal} internal skipped)" if internal else ""))

    if not all_jobs:
        print("!!! 0 jobs parsed — NOT writing CSV (guard against wiping good data)")
        sys.exit(1)

    seen = load_first_seen()
    for j in all_jobs:
        j["date"] = seen.get(row_key(j), TODAY)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_jobs)

    mc = sum(1 for j in all_jobs if j["position_type"] == "maternity_cover")
    print(f"\nwrote {OUT}: {len(all_jobs)} jobs "
          f"({sum(1 for j in all_jobs if j['department']=='academic_faculty')} academic, "
          f"{sum(1 for j in all_jobs if j['department']=='admin_staff')} admin, "
          f"{mc} maternity_cover, {internal_total} internal skipped)")


if __name__ == "__main__":
    main()
