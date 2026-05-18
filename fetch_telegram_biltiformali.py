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
"""

import asyncio
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
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

TG_API_ID     = int(os.environ["TG_API_ID"])
TG_API_HASH   = os.environ["TG_API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

CSV_COLUMNS = [
    "id", "title", "company", "city", "url",
    "date_posted", "source", "work_type", "sector", "level",
    "employer_type", "raw_text",
]
# ── Claude parsing ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a structured data extractor for an Israeli job board.
You receive a raw Telegram message (in Hebrew or English) from the channel
"מציאת עבודה" (@biltiformali), which focuses on:
  management, third sector / NGOs, education, informal education,
  social welfare — mid-level and above positions.

Your job:
1. Decide if the message is a genuine job posting (is_job: true/false).
   - Not a job: admin announcements, general discussion, ads for services,
     "I'm looking for a job" self-posts, etc.
2. If it IS a job, extract all fields below.

Return ONLY valid JSON, no markdown, no explanation:

{
  "is_job": true,
  "title": "Job title in original language (Hebrew preferred)",
  "company": "Organization name, or null if not mentioned",
  "city": "City/region in Hebrew, or null",
  "url": "Application URL or contact link, or null",
  "work_type": "משרה מלאה | משרה חלקית | פרילנס | התנדבות | null",
  "sector": "ממשלתי | עמותות | חינוך | רווחה | עסקי | אחר | null",
  "level": "בכיר | ניהולי | ביניים | null"
}

If the message is NOT a job: return { "is_job": false }
"""

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


def parse_message(text: str) -> dict | None:
    """Call Claude to parse a single Telegram message. Returns dict or None."""
    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = response.content[0].text.strip()
        data = json.loads(raw)
        return data if data.get("is_job") else None
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [warn] Claude parse error: {e}")
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
            return txt[ent.offset: ent.offset + ent.length]
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

async def scrape(days: int | None = 7, fetch_all: bool = False):
    seen = load_seen()
    jobs = []
    new_seen = set()

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

            # Skip already processed
            if msg.id in seen:
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
                "raw_text":    text[:300].replace("\n", " "),
            })

    # Write CSV
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"jobs_telegram_biltiformali_{today}.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(jobs)

    save_seen(new_seen)

    print(f"\n✓ {len(jobs)} jobs written → {out_path}")
    print(f"  ({len(new_seen)} messages processed, {len(seen)} already seen)")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7,
                        help="How many days back to fetch (default: 7)")
    parser.add_argument("--all", action="store_true",
                        help="Fetch full channel history")
    args = parser.parse_args()

    asyncio.run(scrape(
        days=args.days,
        fetch_all=args.all,
    ))