#!/usr/bin/env python3
"""Diagnostic: dump what's on the Deloitte positions page so we can fix Load More."""
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(user_agent=UA)
    pg.goto("https://careers.deloitte.co.il/positions/", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3000)

    print("position links initially:", pg.locator("a[href*='/position/']").count())

    # Look for anything that looks like a load-more / show-more control
    for sel in ["text=Load More", "text=load more", "text=Show More", "text=עוד",
                "text=טען עוד", "text=הצג עוד", "button", ".load-more", "#load-more",
                "[class*='load']", "[class*='more']", "a.btn", "button.btn"]:
        try:
            loc = pg.locator(sel)
            c = loc.count()
            if c:
                print(f"  selector {sel!r}: {c} match(es)")
                for i in range(min(c, 3)):
                    try:
                        txt = loc.nth(i).inner_text()[:40]
                        vis = loc.nth(i).is_visible()
                        print(f"      [{i}] visible={vis} text={txt!r}")
                    except Exception:
                        pass
        except Exception:
            pass

    # Try scrolling to bottom a few times to see if it lazy-loads
    print("\n-- trying scroll --")
    for i in range(8):
        pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        pg.wait_for_timeout(1500)
        n = pg.locator("a[href*='/position/']").count()
        print(f"  after scroll {i+1}: {n} position links")

    b.close()
