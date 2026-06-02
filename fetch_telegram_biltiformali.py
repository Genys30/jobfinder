"""
fetch_telegram_biltiformali.py
──────────────────────────────
Scrapes job posts from the public Telegram channel @biltiformali,
parses them with Claude, and outputs a dated CSV for jobfinder.

Setup (one-time):
    pip install telethon anthropic python-dotenv

Credentials needed in .env (or env vars):
    TG_API_ID=...          # from https://my.telegram.org
    TG_API_HASH=...        # from https://my.telegram.org
    ANTHROPIC_API_KEY=...

Usage:
    python fetch_telegram_biltiformali.py            # last 7 days
    python fetch_telegram_biltiformali.py --days 30  # backfill
    python fetch_telegram_biltiformali.py --all      # full history
    python fetch_telegram_biltiformali.py --days 3 --reparse  # re-evaluate last 3 days
"""

import asyncio
import csv
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────

CHANNEL       = "biltiformali"
SESSION_FILE  = "tg_session"          # Telethon session — keep out of git
SEEN_FILE     = Path("seen_telegram_biltiformali.txt")
OUT_DIR       = Path(".")             # where dated CSVs land
SOURCE_NAME   = "Biltiformali-Telegram"

# Vacancies stay visible for this many days from their publication date
# (date_posted), then drop out of the CSV. 7 = today + 6 previous days.
RETENTION_DAYS = 7

TG_API_ID     = int(os.environ["TG_API_ID"])
TG_API_HASH   = os.environ["TG_API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

CSV_COLUMNS = [
    "id", "title", "company", "city", "url",
    "date_posted", "source", "work_type", "sector", "level",
    "employer_type", "description", "raw_text",
]
# ── Claude parsing ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a structured data extractor for an Israeli job board.
You receive a raw Telegram message (in Hebrew or English) from the channel
"מציאת עבודה" (@biltiformali). This channel posts job vacancies across all
sectors and all seniority levels.

IMPORTANT: Almost every message in this channel is a job vacancy. Default to
is_job: true. Accept jobs of ANY seniority (junior, coordinator, administrative,
mid, senior, management) and ANY sector (government, NGO/nonprofit, education,
welfare, academia, business, etc.). Seniority and sector must NEVER be a reason
to reject a posting.

Set is_job: false ONLY when the message is clearly NOT a vacancy, such as:
  - greetings / holiday wishes / channel rules / admin announcements
  - advertisements for paid services (courses, CV-writing, coaching)
  - "I am looking for a job" self-posts (a person seeking work, not an opening)
  - polls, general discussion, or other non-vacancy chatter
When in doubt, prefer is_job: true.

If it IS a job, extract all fields below.

Return ONLY valid JSON, no markdown, no explanation:

{
  "is_job": true,
  "title": "Job title in original language (Hebrew preferred)",
  "company": "Organization name, or null if not mentioned",
  "city": "City/region in Hebrew, or null",
  "url": "Application URL or contact link, or null",
  "work_type": "משרה מלאה | משרה חלקית | פרילנס | התנדבות | null",
  "sector": "ממשלתי | עמותות | חינוך | רווחה | אקדמיה | עסקי | אחר | null",
  "level": "בכיר | ניהולי | ביניים | זוטר | null"
}

If the message is NOT a job: return { "is_job": false }

OUTPUT RULES (critical):
- Return ONLY the raw JSON object. No markdown, no code fences, no explanation
  before or after it.
- Inside string values, NEVER use the standard double-quote character ("). For
  Hebrew abbreviations that normally take gershayim (e.g. עו״ס, מתנ״ס, חל״ד),
  use the gershayim character ״ (U+05F4), not ".
"""

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


def extract_json(raw: str) -> dict | None:
    """
    Best-effort extraction of a single JSON object from a model response.

    Handles common failure modes:
      - markdown ```json ... ``` fences
      - prose before/after the JSON object
      - stray double-quotes inside Hebrew abbreviations (e.g. עו"ס, מתנ"ס),
        which break naive json.loads — we repair quotes that sit between two
        Hebrew letters by converting them to the gershayim character (U+05F4).
    """
    if not raw:
        return None

    # Strip markdown fences anywhere in the text
    s = re.sub(r'```(?:json)?', '', raw).strip()

    # Isolate the first balanced {...} block
    start = s.find('{')
    if start == -1:
        return None
    depth = 0
    end = -1
    for i in range(start, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    block = s[start:end]

    # Attempt 1: parse as-is
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        pass

    # Attempt 2: repair inner quotes sitting between Hebrew letters
    # (Hebrew abbreviations like עו"ס / מתנ"ס embed a literal " inside a value).
    repaired = re.sub(r'(?<=[\u0590-\u05FF])"(?=[\u0590-\u05FF])', '\u05F4', block)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def parse_message(text: str, _retry: bool = True) -> dict | None:
    """Call Claude to parse a single Telegram message. Returns dict or None."""
    raw = ""
    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = response.content[0].text.strip()
        data = extract_json(raw)
        if data is None:
            # One retry with an explicit format reminder before giving up.
            if _retry:
                reminder = (
                    text
                    + "\n\n---\nReturn ONLY a valid JSON object. Do not use markdown. "
                      'Inside string values do not use the " character; for Hebrew '
                      "abbreviations use the gershayim character \u05F4 instead."
                )
                return parse_message(reminder, _retry=False)
            print(f"  [warn] JSON parse failed | raw: {repr(raw[:100])}")
            return None
        return data if data.get("is_job") else None
    except Exception as e:
        print(f"  [warn] API error: {type(e).__name__}: {e}")
        return None


# ── URL extraction from Telegram message entities ───────────────────────────

def extract_url(message) -> str | None:
    """Pull the first URL from message entities (inline buttons / links)."""
    if not message.entities:
        return None
    for ent in message.entities:
        if isinstance(ent, MessageEntityTextUrl):
            return ent.url
        if isinstance(ent, MessageEntityUrl):
            txt = message.message or ""
            raw = txt[ent.offset: ent.offset + ent.length]
            raw = re.sub(r'^https?://', '', raw)
            return 'https://' + raw
    # Fallback: regex in plain text
    urls = re.findall(r'https?://\S+', message.message or "")
    return urls[0] if urls else None


# ── Seen-IDs dedup ────────────────────────────────────────────────────────────

def load_seen() -> set[int]:
    if SEEN_FILE.exists():
        return {int(x) for x in SEEN_FILE.read_text().splitlines() if x.strip()}
    return set()


def save_seen(ids: set[int]):
    existing = load_seen()
    all_ids = existing | ids
    SEEN_FILE.write_text("\n".join(str(i) for i in sorted(all_ids)))


# ── Main ──────────────────────────────────────────────────────────────────────

async def scrape(days: int | None = 7, fetch_all: bool = False, reparse: bool = False):
    seen = load_seen()
    jobs = []
    new_seen = set()
    if reparse:
        print("  [reparse] ignoring seen-cache for messages in this window")

    cutoff = None
    if not fetch_all and days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with TelegramClient(SESSION_FILE, TG_API_ID, TG_API_HASH) as client:
        print(f"Connected. Fetching messages from @{CHANNEL}...")
        channel = await client.get_entity(CHANNEL)

        async for msg in client.iter_messages(channel, reverse=False):
            # Stop at cutoff
            if cutoff and msg.date < cutoff:
                break

            # Skip already processed (unless reparsing this window)
            if msg.id in seen and not reparse:
                continue

            text = msg.message or ""
            if len(text.strip()) < 20:
                new_seen.add(msg.id)
                continue

            print(f"  → msg {msg.id} ({msg.date.date()}) — parsing...")
            parsed = parse_message(text)
            new_seen.add(msg.id)

            if not parsed:
                continue

            # Build job row
            msg_url = extract_url(msg) or parsed.get("url") or f"https://t.me/{CHANNEL}/{msg.id}"
            job_id  = hashlib.md5(f"{CHANNEL}_{msg.id}".encode()).hexdigest()[:12]

            jobs.append({
                "id":          job_id,
                "title":       parsed.get("title") or "",
                "company":     parsed.get("company") or "",
                "city":        parsed.get("city") or "",
                "url":         msg_url,
                "date_posted": msg.date.strftime("%Y-%m-%d"),
                "employer_type": "Nonprofit/NGO",
                "source":      SOURCE_NAME,
                "work_type":   parsed.get("work_type") or "",
                "sector":      parsed.get("sector") or "",
                "level":       parsed.get("level") or "",
                "description": text[:1500].replace("\n", " "),
                "raw_text":    text[:300].replace("\n", " "),
            })

    # ── Merge with today's existing CSV, then prune by date_posted ───────────
    # Rationale: a normal --days 1 run only finds *newly seen* messages, so it
    # must NOT overwrite jobs captured earlier (which would wipe the file).
    # Instead we merge new jobs into whatever is already in today's CSV, dedup
    # by id, and drop anything whose date_posted is older than RETENTION_DAYS.
    today    = datetime.now().strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"jobs_telegram_biltiformali_{today}.csv"

    existing = []
    if out_path.exists():
        with open(out_path, newline="", encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))

    # Newly scraped jobs take precedence over older copies of the same id.
    merged = {}
    for row in existing:
        if row.get("id"):
            merged[row["id"]] = row
    for row in jobs:
        merged[row["id"]] = row

    # Keep only vacancies published within the retention window.
    cutoff_date = (date.today() - timedelta(days=RETENTION_DAYS - 1)).isoformat()
    final_rows = [r for r in merged.values()
                  if (r.get("date_posted") or "") >= cutoff_date]
    # Newest first.
    final_rows.sort(key=lambda r: r.get("date_posted") or "", reverse=True)

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(final_rows)

    save_seen(new_seen)

    pruned = len(merged) - len(final_rows)
    print(f"\n✓ {len(final_rows)} jobs in {out_path}")
    print(f"  ({len(jobs)} fetched this run, {len(merged) - len(jobs)} kept from before, "
          f"{pruned} pruned as older than {RETENTION_DAYS} days)")
    print(f"  ({len(new_seen)} messages processed, {len(seen)} already seen)")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7,
                        help="How many days back to fetch (default: 7)")
    parser.add_argument("--all", action="store_true",
                        help="Fetch full channel history")
    parser.add_argument("--reparse", action="store_true",
                        help="Re-evaluate messages in the window even if already seen "
                             "(use to backfill after a prompt change)")
    args = parser.parse_args()

    asyncio.run(scrape(
        days=args.days,
        fetch_all=args.all,
        reparse=args.reparse,
    ))