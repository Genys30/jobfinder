#!/usr/bin/env python3
"""
fetch_hapoalim.py — Scrapes open positions at Bank Hapoalim (בנק הפועלים) from
the bank's own careers site.

  Lobby:   https://www.bankhapoalim.co.il/he/jobs-site/lobby   (canonical "משרות פנויות")
  Landing: https://www.bankhapoalim.co.il/he/jobs-site         (featured subset)
  CMS: Drupal 10.2 (Views), server-rendered, behind an **Imperva/Incapsula WAF**.
  Plain requests get an /_Incapsula_Resource challenge; datacenter IPs are blocked.
  → **curl_cffi** (chrome TLS impersonation) clears it from an Israeli IP, like HIT.
  LOCAL-ONLY (cannot run in GitHub Actions — datacenter IP is blocked).

  Listing cards (on lobby + landing):
    a.views-row.job[href="/he/node/{nid}"]   → real per-job URL (dedup key = node id)
      .job-name  → title
      .job-area  → area (גוש דן / השפלה …)  → location
  The card has no job-type/description, so we fetch each node detail page
  (/he/node/{nid}, article.job-page-single) for description (.job-content) and
  division (חטיבה …). The detail fetch also validates the node is a live job page
  (drops 403/404/non-job nodes — keeps the feed clean of dead listings).

  Enumeration is "best practice": seed from lobby + landing, AUTO-FOLLOW the Drupal
  pager (?page=N) collecting a.views-row.job cards until no new node ids appear
  (today the view has no pager → stops at the current set; auto-scales if a pager
  is added later). Sitemap is intentionally NOT used — it lists ~141 mixed
  node URLs incl. old/closed pages (would pollute the feed, like HOOP's dead cards).

  position_type is title-based (the page has no explicit scope field): student
  roles → part_time (Anna's choice); מתמחה/intern → internship; חל"ד → maternity_cover.

  No publish date on the page → first_seen/date keyed by node URL (LinkedIn/Tel-Hai
  pattern: preserves the discovery date across runs).

Output: hapoalim_jobs_YYYY-MM-DD.csv
Usage:  py fetch_hapoalim.py        (local only; needs curl_cffi + beautifulsoup4)
"""

import csv, re, sys, glob, time
from datetime import date, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("curl_cffi not installed. Run: pip install curl_cffi")
    sys.exit(1)

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"hapoalim_jobs_{TODAY}.csv"
SOURCE      = "hapoalim"
COMPANY     = "בנק הפועלים"
BASE        = "https://www.bankhapoalim.co.il"
HOME        = BASE + "/he"
LOBBY       = BASE + "/he/jobs-site/lobby"
LANDING     = BASE + "/he/jobs-site"
MAX_PAGES   = 25          # safety cap for pager auto-follow
DETAIL_SLEEP = 0.7        # politeness between node detail fetches

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

NODE_RX = re.compile(r"/he/node/(\d+)")


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


# ── title → position_type (whitelisted values only) ─────────────────────────
def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"סטודנט", t):              # Anna's choice: student → part_time
        return "part_time"
    if re.search(r"חצי משרה|משרה חלקית|חלקית", t):
        return "part_time"
    return ""                                # full / unspecified → full_time


def load_first_seen():
    """Most recent previous hapoalim CSV → {url: date}. Per-job /node/ URLs → key by URL."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("hapoalim_jobs_*.csv"))
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


def blocked(text):
    """A real Incapsula block is a tiny page with the resource and no content."""
    return ("_Incapsula_Resource" in text and len(text) < 20000
            and "job" not in text.lower())


def make_session():
    """curl_cffi chrome impersonation clears Incapsula from an Israeli IP.
    Warm up on the home page so the WAF issues its session cookies."""
    s = cffi_requests.Session(impersonate="chrome")
    s.headers.update(HEADERS)
    try:
        s.get(HOME, timeout=30)
        time.sleep(1.2)
    except Exception as e:
        print(f"  (warm-up skipped: {e})")
    return s


def fetch(session, url):
    """GET with retries; treat an Incapsula challenge page as a failure."""
    last = None
    for attempt in range(1, 4):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 200 and r.text and not blocked(r.text):
                return r.text
            last = f"HTTP {r.status_code}" + (" (WAF challenge)" if r.text and blocked(r.text) else "")
        except Exception as e:
            last = str(e)
        time.sleep(2.0)
    print(f"  ✗ {url} — {last}")
    return None


def cards_on(html):
    """Return [(nid, title, area)] for a.views-row.job cards on a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select("a.views-row.job, a.job[href*='/he/node/']"):
        m = NODE_RX.search(a.get("href", ""))
        if not m:
            continue
        nid = m.group(1)
        name = a.select_one(".job-name")
        area = a.select_one(".job-area")
        out.append((nid, clean(name.get_text(" ", strip=True)) if name else "",
                    clean(area.get_text(" ", strip=True)) if area else ""))
    return out


def enumerate_cards(session):
    """Seed from landing + lobby, auto-follow the pager until no new node ids.
    Returns ordered {nid: (title, area)}."""
    found = {}

    # landing (featured subset)
    html = fetch(session, LANDING)
    if html:
        for nid, title, area in cards_on(html):
            found.setdefault(nid, (title, area))

    # lobby + pager auto-follow (Drupal ?page=N, 0-indexed)
    for page in range(0, MAX_PAGES):
        url = LOBBY if page == 0 else f"{LOBBY}?page={page}"
        html = fetch(session, url)
        if not html:
            break
        page_cards = cards_on(html)
        new = [c for c in page_cards if c[0] not in found]
        for nid, title, area in page_cards:
            found.setdefault(nid, (title, area))
        print(f"  lobby page {page}: {len(page_cards)} cards ({len(new)} new)")
        if not new:                 # no pager / end of results
            break

    return found


def fetch_detail(session, nid):
    """Fetch /he/node/{nid}; return (alive, title, division, description).
    alive=False drops the node from the feed (403/404/redirect/not a job page)."""
    url = f"{BASE}/he/node/{nid}"
    html = fetch(session, url)
    if not html:
        return False, "", "", ""
    soup = BeautifulSoup(html, "html.parser")
    art = soup.select_one("article.job-page-single, article[data-history-node-id]")
    if not art:
        return False, "", "", ""

    title_el = soup.select_one(".title-job .title") or soup.select_one(".title-job")
    title = clean(title_el.get_text(" ", strip=True)) if title_el else ""

    # division (department): the "חטיבה …" link (aria-label or text).
    # NOTE: .job-category-area is the AREA/region (== location), NOT the division,
    # so we must not read department from it.
    division = ""
    for a in art.find_all("a"):
        al = clean(a.get("aria-label") or "")
        if "חטיבה" in al:
            division = al
            break
        txt = clean(a.get_text(" ", strip=True))
        if "חטיבה" in txt:
            division = txt
            break

    # description: .job-content (fallback to .job-category text)
    desc_el = soup.select_one(".job-content")
    if desc_el:
        description = clean(desc_el.get_text(" ", strip=True))
    else:
        cat = soup.select_one(".job-category")
        description = clean(cat.get_text(" ", strip=True)) if cat else ""

    return True, title, division, description[:1500]


def scrape():
    first_seen = load_first_seen()
    session = make_session()

    print(f"\n[Bank Hapoalim] enumerating cards (lobby + landing)…")
    cards = enumerate_cards(session)
    print(f"  → {len(cards)} unique job nodes")

    jobs = []
    dropped = 0
    for nid, (card_title, area) in cards.items():
        url = f"{BASE}/he/node/{nid}"
        alive, d_title, division, description = fetch_detail(session, nid)
        time.sleep(DETAIL_SLEEP)
        if not alive:
            dropped += 1
            print(f"  – node {nid}: not a live job page — dropped")
            continue
        title = card_title or d_title
        if not title:
            dropped += 1
            continue
        if not description:
            description = area      # minimal fallback so the pop-up isn't empty
        pt = title_to_position_type(title)
        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       area or "ישראל",
            "date":           first_seen.get(url, TODAY),
            "url":            url,
            "department":     division,
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    description,
            "position_type":  pt,
        })
        tag = f" [{pt}]" if pt else ""
        print(f"  • node {nid}: {title[:46]}{tag}  | desc {len(description)}c"
              f"{(' | ' + division) if division else ''}")

    print(f"\n  → {len(jobs)} jobs ({dropped} dropped)")
    return jobs


def main():
    jobs = scrape()

    # 0-row guard: skip CSV write so the health check falls back to yesterday's file.
    if not jobs:
        print("\n⚠️  No jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\n✅ Wrote {len(jobs)} jobs → {OUTPUT_FILE}")

    print("\nNext steps:")
    print("  git add -f hapoalim_jobs_*.csv")
    print("  git add fetch_hapoalim.py run_fetch.bat")
    print("  git commit -m 'feat: add Bank Hapoalim careers scraper'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
