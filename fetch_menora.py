import sys, csv, os
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE   = "menora"
COMPANY  = "מנורה מבטחים"
LIST_URL = "https://www.menoramivt.co.il/job-posting/open-position"
OUT_CSV  = f"{SOURCE}_jobs_{date.today()}.csv"
FIELDS   = ["title", "company", "location", "department", "description", "url", "date_posted", "first_seen", "source"]


def load_prior():
    seen = {}
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                seen[row["title"]] = row["first_seen"]
    return seen


def parse_cards(html, prior, today):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select("div.divLayer"):
        title_el = card.select_one("div.positionName-re")
        dept_el  = card.select_one("span.position-type-text")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        dept  = dept_el.get_text(strip=True) if dept_el else ""
        if not title:
            continue
        jobs.append({
            "title":       title,
            "company":     COMPANY,
            "location":    "",
            "department":  dept,
            "description": "",
            "url":         LIST_URL,
            "date_posted": today,
            "first_seen":  prior.get(title, today),
            "source":      SOURCE,
        })
    return jobs


def main():
    today = str(date.today())
    prior = load_prior()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="he-IL",
        )
        page = ctx.new_page()
        try:
            page.goto(LIST_URL, timeout=40000, wait_until="domcontentloaded")
        except Exception:
            pass
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()

    jobs = parse_cards(html, prior, today)
    print(f"[menora] {len(jobs)} jobs")

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(jobs)
    print(f"[menora] wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
