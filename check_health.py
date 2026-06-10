# -*- coding: utf-8 -*-
"""
check_health.py — JobFinder source health-check agent.

Run after all scrapers (run_fetch.bat step, before rclone/commit).
For every known source it verifies that:
  1. A fresh dated CSV exists (today for local sources, <=1 day for CI sources)
  2. The file is not empty / header-only
  3. Required columns are present (title, company, url, date)
  4. Row count has not collapsed vs the previous file (>50% drop = WARN)

Prints a console report and writes health_report.json (commit it so the
status is readable from a phone via the raw GitHub URL).

Always exits 0 so run_fetch.bat is never aborted.

Usage:
    python check_health.py                 # normal run (today)
    python check_health.py --date 2026-06-09   # check as of another date
    python check_health.py --max-age 2    # relax freshness for all sources
"""

import argparse
import csv
import glob
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------
# pattern    : CSV filename prefix; files are "{pattern}_{YYYY-MM-DD}.csv"
# where      : "local" (run_fetch.bat), "ci" (GitHub Actions / fetch_jobs.py),
#              "manual" (uploaded by hand)
# allow_zero : True if 0 data rows is acceptable (downgrades FAIL -> WARN)
#
# Freshness expectations (overridable with --max-age):
#   local  -> file dated today (age 0)
#   ci     -> file dated today or yesterday (age <= 1)
#   manual -> age <= 2, and problems are reported as WARN, not FAIL

# Each entry is a list of acceptable aliases — at least one must be present.
# Per-source override: add "columns": [...] to the SOURCES entry.
REQUIRED_COLUMNS = [["title"], ["company"], ["url"], ["date", "date_posted"]]
COLUMNS_NO_COMPANY = [["title"], ["url"], ["date", "date_posted"]]

SOURCES = [
    # --- local: run_fetch.bat standalone scrapers ---
    {"name": "Telegram",        "pattern": "jobs_telegram_biltiformali", "where": "local"},
    {"name": "Rambam",          "pattern": "rambam_jobs",        "where": "local"},
    {"name": "BGU",             "pattern": "bgu_jobs",           "where": "local", "allow_zero": True},
    {"name": "Maccabi",         "pattern": "maccabi_jobs",       "where": "local"},
    {"name": "MOD",             "pattern": "mod_jobs",           "where": "local"},
    {"name": "Clalit",          "pattern": "clalit_jobs",        "where": "local"},
    {"name": "TAU",             "pattern": "tau_jobs",           "where": "local"},
    {"name": "Haifa Univ",      "pattern": "haifa_jobs",         "where": "local"},
    {"name": "Bar-Ilan",        "pattern": "bar_jobs",           "where": "local", "columns": COLUMNS_NO_COMPANY},
    {"name": "Ichilov",         "pattern": "topmatch_jobs",      "where": "local"},
    {"name": "GotFriends",      "pattern": "gotfriends_jobs",    "where": "local"},
    {"name": "HUJI positions",  "pattern": "huji_positions",     "where": "local"},
    {"name": "Shaare Zedek",    "pattern": "szmc_jobs",          "where": "local"},
    {"name": "Hadassah",        "pattern": "hadassah_jobs",      "where": "local"},
    {"name": "Deloitte",        "pattern": "deloitte_jobs",      "where": "local"},
    {"name": "EY",              "pattern": "ey_jobs",            "where": "local"},
    {"name": "BIS",             "pattern": "bis_jobs",           "where": "local"},
    {"name": "Joint (JDC)",     "pattern": "joint_jobs",         "where": "local"},
    {"name": "Osem-Nestle",     "pattern": "osem_jobs",          "where": "local"},
    {"name": "Teva",            "pattern": "teva_jobs",          "where": "local"},
    # --- ci: fetch_jobs.py (GitHub Actions nightly and/or local step) ---
    {"name": "Comeet",          "pattern": "comeet_jobs",        "where": "ci"},
    {"name": "Greenhouse",      "pattern": "greenhouse_jobs",    "where": "ci"},
    {"name": "Lever",           "pattern": "lever_jobs",         "where": "ci"},
    {"name": "Ashby",           "pattern": "ashby_jobs",         "where": "ci", "allow_zero": True},
    {"name": "Workable",        "pattern": "workable_jobs",      "where": "ci", "allow_zero": True},
    {"name": "Mitam",           "pattern": "mitam_jobs",         "where": "ci"},
    {"name": "Weizmann",        "pattern": "weizmann_jobs",      "where": "ci"},
    {"name": "Technion",        "pattern": "technion_jobs",      "where": "ci"},
    {"name": "Leumit",          "pattern": "leumit_jobs",        "where": "ci"},
    {"name": "Meuhedet",        "pattern": "meuhedet_jobs",      "where": "ci"},
    {"name": "Movement",        "pattern": "movement_jobs",      "where": "ci"},
    {"name": "Innovation IL",   "pattern": "innovation_israel_jobs", "where": "ci"},
    {"name": "HUJI Alumni",     "pattern": "huji_alumni_jobs",   "where": "ci"},
    # --- manual ---
    {"name": "LinkedIn",        "pattern": "linkedin_jobs",      "where": "manual"},
]

MAX_AGE = {"local": 0, "ci": 1, "manual": 2}
DROP_THRESHOLD = 0.5      # WARN if rows fall below 50% of the previous file
DROP_MIN_PREV = 20        # only apply the drop check if prev file had >= 20 rows
REPORT_FILE = "health_report.json"

DATE_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})\.csv$")


def find_dated_files(pattern):
    """Return [(date, filename)] for all files matching pattern_YYYY-MM-DD.csv,
    newest first. Anchored to the start of the filename so e.g. 'bar_jobs'
    does not match 'sidebar_jobs'."""
    out = []
    for f in glob.glob(pattern + "_*.csv"):
        m = DATE_RE.search(f)
        if m and os.path.basename(f) == "%s_%s.csv" % (pattern, m.group(1)):
            try:
                out.append((datetime.strptime(m.group(1), "%Y-%m-%d").date(), f))
            except ValueError:
                pass
    return sorted(out, reverse=True)


def read_csv_stats(path):
    """Return (row_count, header_list). utf-8-sig strips the BOM that
    Windows-generated CSVs carry on the first column header."""
    with io.open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None) or []
        rows = sum(1 for r in reader if any((c or "").strip() for c in r))
    return rows, [h.strip().lower() for h in header]


def check_source(src, today, max_age_override):
    """Check one source. Returns a result dict."""
    res = {
        "name": src["name"], "pattern": src["pattern"], "where": src["where"],
        "status": "OK", "file": None, "file_date": None, "age_days": None,
        "rows": None, "prev_rows": None, "messages": [],
    }
    allow_zero = src.get("allow_zero", False)
    is_manual = src["where"] == "manual"
    max_age = max_age_override if max_age_override is not None else MAX_AGE[src["where"]]

    def fail(msg):
        res["status"] = "WARN" if is_manual else "FAIL"
        res["messages"].append(msg)

    def warn(msg):
        if res["status"] != "FAIL":
            res["status"] = "WARN"
        res["messages"].append(msg)

    files = find_dated_files(src["pattern"])
    if not files:
        fail("no CSV files found at all")
        return res

    fdate, fname = files[0]
    age = (today - fdate).days
    res.update({"file": fname, "file_date": str(fdate), "age_days": age})

    if age > max_age:
        fail("latest file is %d day(s) old (%s)" % (age, fdate))
        # Still inspect the stale file below so the report shows its contents.

    # --- content checks ---
    try:
        rows, header = read_csv_stats(fname)
    except Exception as e:
        fail("cannot read file: %s" % e)
        return res
    res["rows"] = rows

    required = src.get("columns", REQUIRED_COLUMNS)
    missing = [a[0] for a in required if not any(c in header for c in a)]
    if missing:
        fail("missing columns: %s" % ", ".join(missing))

    if rows == 0:
        if allow_zero:
            warn("0 rows (known to happen for this source)")
        else:
            fail("file is empty / header-only")

    # --- row-count drop vs previous file ---
    if len(files) > 1 and rows > 0:
        try:
            prev_rows, _ = read_csv_stats(files[1][1])
            res["prev_rows"] = prev_rows
            if prev_rows >= DROP_MIN_PREV and rows < prev_rows * DROP_THRESHOLD:
                warn("row count dropped %d -> %d (-%d%%) vs %s"
                     % (prev_rows, rows, round(100 - 100.0 * rows / prev_rows),
                        files[1][0]))
        except Exception:
            pass  # previous file unreadable — not this source's problem today

    return res


def main():
    ap = argparse.ArgumentParser(description="JobFinder source health check")
    ap.add_argument("--date", help="check as of this date (YYYY-MM-DD), default today")
    ap.add_argument("--max-age", type=int, default=None,
                    help="override max allowed file age in days for ALL sources")
    args = ap.parse_args()

    today = (datetime.strptime(args.date, "%Y-%m-%d").date()
             if args.date else date.today())

    results = [check_source(s, today, args.max_age) for s in SOURCES]

    # --- console report ---
    print("")
    print("=" * 62)
    print(" JobFinder health check — %s" % today)
    print("=" * 62)
    order = {"FAIL": 0, "WARN": 1, "OK": 2}
    for r in sorted(results, key=lambda r: (order[r["status"]], r["name"])):
        rows = "-" if r["rows"] is None else str(r["rows"])
        line = " [%-4s] %-15s %6s rows" % (r["status"], r["name"], rows)
        if r["messages"]:
            line += "   " + "; ".join(r["messages"])
        print(line)

    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_warn = sum(1 for r in results if r["status"] == "WARN")
    n_ok = sum(1 for r in results if r["status"] == "OK")
    overall = "FAIL" if n_fail else ("WARN" if n_warn else "OK")
    print("-" * 62)
    print(" TOTAL: %d OK, %d WARN, %d FAIL  ->  overall %s"
          % (n_ok, n_warn, n_fail, overall))
    print("=" * 62)
    print("")

    # --- JSON report (committed to the repo, readable from a phone) ---
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "check_date": str(today),
        "overall": overall,
        "ok": n_ok, "warn": n_warn, "fail": n_fail,
        "sources": results,
    }
    try:
        with io.open(REPORT_FILE, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print("Report written to %s" % REPORT_FILE)
    except Exception as e:
        print("WARNING: could not write %s: %s" % (REPORT_FILE, e))

    sys.exit(0)  # never break run_fetch.bat


if __name__ == "__main__":
    main()
