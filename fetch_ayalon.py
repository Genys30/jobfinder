import sys, csv, os, re, json
from datetime import date
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE   = "ayalon"
COMPANY  = "איילון"
BASE_URL = "https://www.ayalon-ins.co.il"
LIST_URL = f"{BASE_URL}/career/jobs"
OUT_CSV  = f"{SOURCE}_jobs_{date.today()}.csv"
FIELDS   = ["title", "company", "location", "department", "description", "url", "date_posted", "first_seen", "source"]

PROFESSION_MAP = {
    7:  "טכנולוגיות ומערכות מידע",
    8:  "חיתום",
    9:  "יישוב תביעות",
    10: "בק אופיס ותפעול",
    11: "שירות לקוחות שימור ומכירות",
    12: "פיננסים השקעות ושוק ההון",
    13: "מטה ואדמינסטרציה",
}


class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def get_text(self):
        return " ".join(self.parts).strip()


def strip_html(html):
    if not html:
        return ""
    p = _StripHTML()
    p.feed(html)
    return re.sub(r"\s+", " ", p.get_text()).strip()


def load_prior():
    seen = {}
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                seen[row["url"]] = row["first_seen"]
    return seen


def fetch_jobs():
    captured = {}

    def on_response(resp):
        url = resp.url
        # Only capture the main jobs endpoint — not jobsareas/jobsproffesoins/jobspage
        is_jobs_api = url.rstrip("/").endswith("/api/careers") and "json" in resp.headers.get("content-type", "")
        if is_jobs_api and not captured:
            try:
                body = resp.body()
                data = json.loads(body)
                if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                    items = data["data"]
                    if items and "jobDescription" in items[0]:
                        captured["data"] = items
            except Exception:
                pass

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
        page.on("response", on_response)
        try:
            page.goto(LIST_URL, timeout=40000, wait_until="domcontentloaded")
        except Exception:
            pass
        page.wait_for_timeout(8000)
        browser.close()

    return captured.get("data", [])


def main():
    today = str(date.today())
    prior = load_prior()

    raw = fetch_jobs()
    print(f"[ayalon] raw jobs: {len(raw)}")

    jobs = []
    seen_urls = set()
    for item in raw:
        title = (item.get("jobDescription") or "").strip()
        if not title:
            continue
        order_id = item.get("orderId") or ""
        url      = f"{BASE_URL}/career/jobs/{order_id}" if order_id else LIST_URL
        if url in seen_urls:
            continue
        seen_urls.add(url)
        location = (item.get("workArea") or "").strip()
        dept_id  = item.get("proffesionID") or 0
        dept     = PROFESSION_MAP.get(dept_id, "")
        desc     = strip_html(item.get("notes") or "")
        jobs.append({
            "title":       title,
            "company":     COMPANY,
            "location":    location,
            "department":  dept,
            "description": desc,
            "url":         url,
            "date_posted": today,
            "first_seen":  prior.get(url, today),
            "source":      SOURCE,
        })

    print(f"[ayalon] {len(jobs)} jobs")
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(jobs)
    print(f"[ayalon] wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
