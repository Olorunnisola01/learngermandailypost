"""
extract_cookies_simple.py
Connects to Chrome that is already running with --remote-debugging-port=9222,
grabs YouTube/Google cookies, saves them, and pushes STEEL_SESSION_CONTEXT to GitHub.
Run via RUN_COOKIE_EXTRACTOR.bat — do NOT run this directly.
"""
import json, os, subprocess, sys, urllib.request

REMOTE_PORT = 9222
REPO_DIR    = os.path.dirname(os.path.abspath(__file__))
GITHUB_REPO = "Olorunnisola01/learngermandailypost"

def main():
    # Verify Chrome debug port is reachable
    try:
        urllib.request.urlopen(f"http://localhost:{REMOTE_PORT}/json/version", timeout=5)
    except Exception as e:
        print(f"ERROR: Chrome debug port not reachable: {e}")
        print("Make sure you ran this script via RUN_COOKIE_EXTRACTOR.bat")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    cookies = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(f"http://localhost:{REMOTE_PORT}")
        ctx = browser.contexts[0] if browser.contexts else None
        if not ctx:
            print("ERROR: No browser context found")
            sys.exit(1)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        raw = ctx.cookies([
            "https://www.youtube.com",
            "https://accounts.google.com",
            "https://www.google.com",
        ])
        print(f"Extracted {len(raw)} cookies from Chrome Profile 12")

        for c in raw:
            entry = {
                "name":     c["name"],
                "value":    c["value"],
                "domain":   c["domain"],
                "path":     c.get("path", "/"),
                "httpOnly": c.get("httpOnly", False),
                "secure":   c.get("secure", False),
                "sameSite": c.get("sameSite", "Lax"),
            }
            if c.get("expires") and c["expires"] > 0:
                entry["expires"] = int(c["expires"])
            cookies.append(entry)

        browser.close()

    ctx_data = {"cookies": cookies, "origins": []}
    out = os.path.join(REPO_DIR, "data", "steel_context.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(ctx_data, f, ensure_ascii=True, indent=2)
    print(f"Saved {len(cookies)} cookies to {out}")

    with open(out, "rb") as f:
        result = subprocess.run(
            ["gh", "secret", "set", "STEEL_SESSION_CONTEXT", "--repo", GITHUB_REPO],
            stdin=f, capture_output=True, text=True
        )
    if result.returncode == 0:
        print("SUCCESS: STEEL_SESSION_CONTEXT secret saved to GitHub!")
    else:
        print(f"ERROR pushing secret: {result.stderr}")
        print(f"You can push it manually: gh secret set STEEL_SESSION_CONTEXT --repo {GITHUB_REPO} < {out}")

if __name__ == "__main__":
    main()
