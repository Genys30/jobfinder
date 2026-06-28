#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_namer.py  --  JobFinder source `namer`

NAMER (נמ"ר) = the Ministry of Interior's national system for personnel tenders
(מכרזי כוח אדם) across Israeli local authorities (עיריות / מועצות מקומיות /
מועצות אזוריות). One feed -> hundreds of authorities. employer-type: public.

API (anonymous, via the Azure APIM gateway; key is the public key embedded in
the site's JS bundle, product `namer-anonymous`):

  GET {APIM}/api/ManageMichrazim/GetAllSiteMichrazim/?basePage=<json>
  Header: Ocp-Apim-Subscription-Key: <key>

`basePage` (filters MUST be null, not [] — empty arrays NRE the server):
  {"page":{"Number":N,"SumItem":100},"search":{"attName":""},
   "sort":[{"attName":"SgiratMichrazDate","desc":false}],
   "statusimFilter":null,"yechidotFilter":null,"mechozotFilter":null,
   "tchumMiktzoiFilter":null,"ramatHascalaFilter":null,"misraYiuditFilter":null,
   "rashuyotFilter":null,"showAllMichrazimInRashut":false}

Response: value.mamageMichrazimsLst[] ; value.page.{number,sumItem,isLast,totalItems}

Each michraz has a real publish date (ptichatMichrazDate) -> no first_seen needed.
Dedup key: misparAsmachta (unique int; oid is NOT unique on its own).

Output: namer_jobs_YYYY-MM-DD.csv  (columns read by normNamer in index.html:
  title, company, location, url, date, deadline, department, description,
  requirements, position_type)

Runs LOCALLY via run_fetch.bat (Israeli IP). Plain JSON over requests; APIM is
Azure (not a gov server), so a CI move may be possible later (see BACKLOG).
"""

import os
import re
import csv
import json
import time
import datetime

APIM = "https://ministryofinteriorapim.azure-api.net/namer-anonymous/v1/api/"
LIST_EP = APIM + "ManageMichrazim/GetAllSiteMichrazim/"
# Per-michraz detail (verified live). The list lacks teurMichraz (the real role
# name), so 'אחר' rows fetch it here. Note: singular "Michraz" path (NOT
# "ManageMichrazim"). GET, asmachta+oid in the path.
DETAIL_EP = APIM + "Michraz/GetSiteMichraz/{asmachta}/{oid}"
SHELL = "https://namerz.moin.gov.il/namer"
ROOT = "https://namerz.moin.gov.il/"
CARD_URL = "https://namerz.moin.gov.il/showexternal/{asmachta}/{oid}"  # SPA detail route (verified live)

# Public key from the site bundle (fallback; fetch_key() re-derives it live so a
# rotation doesn't break us).
FALLBACK_KEY = "401ef4da029a417f9f8da5ad6abad2d0"

PAGE_SIZE = 100
MAX_PAGES = 60          # safety cap (60*100 = 6000, well above ~600 live)
DETAIL_THROTTLE = 0.3   # seconds between detail calls (only fires on 'אחר' rows)
DETAIL_TIMEOUT = 20     # per detail request
TODAY = datetime.date.today().isoformat()
OUT_CSV = "namer_jobs_%s.csv" % TODAY

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Origin": "https://namerz.moin.gov.il",
    "Referer": "https://namerz.moin.gov.il/",
}

# ---------------------------------------------------------------------------
# session (requests primary, curl_cffi fallback)
# ---------------------------------------------------------------------------
_sreq = None
_scffi = None


def _req():
    global _sreq
    if _sreq is None:
        import requests
        s = requests.Session()
        s.headers.update(HEADERS)
        _sreq = s
    return _sreq


def _cffi():
    global _scffi
    if _scffi is None:
        try:
            from curl_cffi import requests as creq
        except Exception:
            return None
        s = creq.Session(impersonate="chrome110")
        s.headers.update(HEADERS)
        _scffi = s
    return _scffi


def http_get(url, params=None, key=None, timeout=60):
    hdr = {"Ocp-Apim-Subscription-Key": key} if key else {}
    try:
        r = _req().get(url, params=params, headers=hdr, timeout=timeout)
        if r.status_code not in (403, 406, 429, 503):
            return r.status_code, r.text
    except Exception:
        pass
    s2 = _cffi()
    if s2 is not None:
        try:
            r = s2.get(url, params=params, headers=hdr, timeout=timeout)
            return r.status_code, r.text
        except Exception:
            return None, ""
    return None, ""


# ---------------------------------------------------------------------------
def fetch_key():
    """Re-derive the public APIM key from the site bundle; fall back to constant."""
    try:
        _, shell = http_get(SHELL)
        m = re.search(r'main\.([0-9a-f]+)\.js', shell or "")
        if m:
            _, js = http_get(ROOT + "main.%s.js" % m.group(1))
            # the key sits near an azure-api reference / Ocp-Apim header literal
            hit = re.search(r'Ocp-Apim-Subscription-Key["\']?\s*[:,]\s*["\']([0-9a-f]{32})["\']',
                            js or "", re.I)
            if hit:
                return hit.group(1)
            hexes = re.findall(r'\b[0-9a-f]{32}\b', js or "")
            if hexes:
                return hexes[0]
    except Exception:
        pass
    return FALLBACK_KEY


def base_page(number):
    return json.dumps({
        "page": {"Number": number, "SumItem": PAGE_SIZE},
        "search": {"attName": ""},
        "sort": [{"attName": "SgiratMichrazDate", "desc": False}],
        "statusimFilter": None,
        "yechidotFilter": None,
        "mechozotFilter": None,
        "tchumMiktzoiFilter": None,
        "ramatHascalaFilter": None,
        "misraYiuditFilter": None,
        "rashuyotFilter": None,
        "showAllMichrazimInRashut": False,
    }, ensure_ascii=False)


def fetch_page(number, key):
    st, txt = http_get(LIST_EP, params={"basePage": base_page(number)}, key=key)
    try:
        j = json.loads(txt)
    except Exception:
        return None, None
    if not isinstance(j, dict) or j.get("success") is not True:
        return None, None
    v = j.get("value") or {}
    return v.get("mamageMichrazimsLst") or [], v.get("page") or {}


# ---------------------------------------------------------------------------
def _date(s):
    """'2026-06-12T00:00:00' -> '2026-06-12'."""
    if not s:
        return ""
    return str(s)[:10]


def _pos_type(title, derug):
    blob = ("%s %s" % (title or "", derug or ""))
    if 'חל"ד' in blob or "חלד" in blob or "חופשת לידה" in blob:
        return "maternity_cover"
    if "חצי משרה" in blob or "חלקית" in blob or "משרה חלקית" in blob:
        return "part_time"
    return ""


def _clean_teur(s):
    """Clean teurMichraz for use as a title: trim, then drop a trailing
    'הארכה' (=extension — an admin note on the tender, not part of the role),
    with an optional leading dash/space. Narrow on purpose; other tails (e.g.
    'מכרז חוזר') are left for a future pass if they show up — see BACKLOG."""
    s = (s or "").strip()
    s = re.sub(r"[\s\-\u2013]*הארכה\s*$", "", s).strip()
    return s


_detail_cache = {}                       # (asm, oid) -> cleaned title
_detail_stats = {"fetched": 0, "ok": 0}  # for the run summary


def fetch_detail_title(asm, oid, key):
    """Variant C: fetch teurMichraz from the per-michraz detail endpoint for an
    'אחר'/blank row. Returns a cleaned title, or '' on ANY failure (the caller
    then falls back to tchumMiktzoi/shemYechida, so a title is always set and
    never reverts to 'אחר'). Throttled; cached per (asm, oid)."""
    if asm is None or oid is None or not key:
        return ""
    ck = (asm, oid)
    if ck in _detail_cache:
        return _detail_cache[ck]
    time.sleep(DETAIL_THROTTLE)
    _detail_stats["fetched"] += 1
    title = ""
    url = DETAIL_EP.format(asmachta=asm, oid=oid)
    st, txt = http_get(url, key=key, timeout=DETAIL_TIMEOUT)
    if st == 200:
        try:
            j = json.loads(txt)
            if isinstance(j, dict) and j.get("success") is True:
                title = _clean_teur((j.get("value") or {}).get("teurMichraz"))
        except Exception:
            title = ""
    if title:
        _detail_stats["ok"] += 1
    _detail_cache[ck] = title
    return title


def map_row(m, key=None):
    """Map one michraz dict -> CSV row dict, or None to skip."""
    if not isinstance(m, dict):
        return None
    # open positions only; skip cancelled / postponed
    if m.get("kodStatus") not in (0, None) and m.get("teurStatus") != "פתוח":
        return None
    if m.get("sibatBitul") or m.get("sibatDchiya"):
        return None

    asm = m.get("misparAsmachta")
    oid = m.get("oid")
    if asm is None:
        return None

    title = (m.get("shemTafkid") or "").strip()
    # `shemTafkid` is literally "אחר" (Other) in ~27% of rows — useless as a
    # title. Variant C: the real role name (teurMichraz, e.g.
    # "כלכלן/ית לאגף וטרינריה") is NOT in the list, only on the detail page, so
    # for these 'אחר'/blank rows we fetch the detail and use teurMichraz. On any
    # failure we fall back to the professional field, then the unit (variant B),
    # so a title is always set and never reverts to "אחר".
    if not title or title == "אחר":
        title = fetch_detail_title(asm, oid, key) \
            or (m.get("tchumMiktzoi") or "").strip() \
            or (m.get("shemYechida") or "").strip()
    if not title:
        return None
    rashut = (m.get("shemRashut") or "").strip()
    machoz = (m.get("shemMachoz") or "").strip()
    tchum = (m.get("tchumMiktzoi") or "").strip()
    yechida = (m.get("shemYechida") or "").strip()
    derug = (m.get("derug") or "").strip()
    hascala = m.get("ramatHascala") or []
    if isinstance(hascala, list):
        hascala = [h.strip() for h in hascala if h and h.strip()]
    else:
        hascala = [str(hascala).strip()] if hascala else []
    ptichat = _date(m.get("ptichatMichrazDate"))
    sgirat = _date(m.get("sgiratMichrazDate"))
    mispar = (m.get("misparMichraz") or "").strip()

    url = CARD_URL.format(asmachta=asm, oid=oid)

    desc_parts = []
    if rashut:
        desc_parts.append("רשות: %s" % rashut)
    if machoz:
        desc_parts.append("מחוז: %s" % machoz)
    if yechida:
        desc_parts.append("יחידה: %s" % yechida)
    if tchum:
        desc_parts.append("תחום: %s" % tchum)
    if derug:
        desc_parts.append("דירוג: %s" % derug)
    if hascala:
        desc_parts.append("רמת השכלה: %s" % ", ".join(hascala))
    if ptichat:
        desc_parts.append("תאריך פרסום: %s" % ptichat)
    if sgirat:
        desc_parts.append("מועד הגשה: %s" % sgirat)
    if mispar:
        desc_parts.append("מספר מכרז: %s" % mispar)
    description = " · ".join(desc_parts)

    department = tchum or yechida
    requirements = "; ".join(hascala)

    return {
        "title": title,
        "company": rashut,
        "location": rashut,
        "url": url,
        "date": ptichat,
        "deadline": sgirat,
        "department": department,
        "description": description,
        "requirements": requirements,
        "position_type": _pos_type(title, derug),
    }


COLUMNS = ["title", "company", "location", "url", "date", "deadline",
           "department", "description", "requirements", "position_type"]


def main():
    key = fetch_key()
    print("[namer] using APIM key %s…%s" % (key[:6], key[-4:]))

    rows = {}            # misparAsmachta -> row (run-level dedup)
    total = None
    for n in range(MAX_PAGES):
        items, page = fetch_page(n, key)
        if items is None:
            print("[namer] page %d: request failed/empty — stopping" % n)
            break
        if total is None and isinstance(page, dict):
            total = page.get("totalItems")
        kept = 0
        for m in items:
            r = map_row(m, key)
            if r:
                rows[m.get("misparAsmachta")] = r
                kept += 1
        print("[namer] page %d: %d items, %d kept (total so far %d / %s)"
              % (n, len(items), kept, len(rows), total))
        if not items:
            break
        if isinstance(page, dict) and page.get("isLast"):
            break
        if total is not None and len(rows) >= total:
            break

    out = list(rows.values())
    print("[namer] %d unique open michrazim" % len(out))
    print("[namer] detail fetches for 'אחר' rows: %d attempted, %d got teurMichraz"
          % (_detail_stats["fetched"], _detail_stats["ok"]))

    if not out:
        # 0-jobs guard: do not overwrite with an empty file (health check then
        # falls back to yesterday's CSV instead of a header-only file).
        print("[namer] 0 jobs parsed — NOT writing CSV (guard).")
        return

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in out:
            w.writerow(r)
    print("[namer] wrote %s (%d rows)" % (OUT_CSV, len(out)))


if __name__ == "__main__":
    main()
