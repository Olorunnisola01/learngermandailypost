# How to build a 24/7 automated YouTube Community quiz poster

This is a complete, from-scratch, step-by-step tutorial for replicating this
exact system on **any** YouTube channel — posting automatically, forever,
without your PC needing to be on. It's written generically: swap in your own
channel handle, content, and posting cadence.

By the end you'll have a GitHub repo that:
- Runs entirely on GitHub's free cloud infrastructure (GitHub Actions)
- Logs into your YouTube channel via a saved browser session (no password ever stored)
- Posts quiz-format Community posts on a schedule you choose
- Tracks what's already been posted so nothing repeats until the whole bank cycles
- Requires zero maintenance beyond an occasional cookie refresh (every few weeks)

---

## 0. Prerequisites

| Requirement | Why |
|---|---|
| A GitHub account | Hosts the repo + runs the free Actions cron |
| [GitHub CLI (`gh`)](https://cli.github.com/) installed and logged in | Used to push secrets from your terminal |
| Python 3.11+ installed locally | Only needed once, to extract cookies |
| A [Steel.dev](https://steel.dev) account + API key | Provides the disposable cloud browser that actually does the posting |
| A browser profile logged into the target YouTube channel's Google account | Source of the session cookies |
| The channel must have **Community posts enabled** (needs 500+ subscribers on most channels, or be eligible via YouTube's rollout) | Without this the Community tab won't exist |

**Why Steel.dev and not just Playwright directly in the Action?** GitHub
Actions runners have no persistent browser profile and no way to "already be
logged in" — you'd have to log in fresh every run, which triggers Google's
bot/anomaly detection. Steel.dev accepts a pre-authenticated cookie set
(`sessionContext`) when creating a session, so every run starts already
logged in, exactly like a real returning visitor.

---

## 1. Create the repo

```bash
mkdir my-channel-autoposter && cd my-channel-autoposter
git init
gh repo create <your-username>/my-channel-autoposter --public --source=. --remote=origin
mkdir -p data scripts .github/workflows
```

---

## 2. Get a Steel.dev API key

1. Sign up at https://steel.dev
2. Copy your API key from the dashboard.
3. You'll push it as a GitHub secret in step 6 — don't commit it to any file.

---

## 3. Extract cookies from a logged-in browser session

This is the trickiest step because **modern Chrome (v127+) encrypts cookies
with "App-Bound Encryption"**, which cannot be decrypted by an external
script — even with full disk access. You have two options:

### Option A (recommended): use a non-Chrome Chromium browser
Any Chromium-based browser that still uses the older, standard **v10
AES-GCM** cookie encryption works. Examples: ixBrowser, older Chrome
installs, Brave (varies by version), Chromium itself. Log into the target
channel's Google account in a profile in that browser, then close the
browser completely (the cookie DB file is locked while the browser is open).

### Option B: manually export cookies
Use a browser extension like "Get cookies.txt" or similar to export cookies
for `youtube.com` and `google.com` as JSON, then hand-convert to the shape
in step 3.3 below. Slower, but sidesteps encryption entirely.

### 3.1 Find your profile's cookie database

Typical Windows path pattern:
```
%APPDATA%\<Browser>\Browser Data\<profile-folder-hash>\Default\Network\Cookies
%APPDATA%\<Browser>\Browser Data\<profile-folder-hash>\Local State   <- holds the encryption key
```
On macOS/Linux the equivalent lives under `~/Library/Application Support/...`
or `~/.config/...` — the `Local State` + `Network/Cookies` pairing is the
same across Chromium-based browsers.

If you have multiple profiles, identify the right one by its icon filename
in the profile picker, or by opening each `Local State` file and checking
`profile.info_cache` for the display name.

### 3.2 Install the Python decryption dependencies
```bash
pip install pycryptodome pywin32   # pywin32 is Windows-only, for DPAPI access
```

### 3.3 The extraction script

Save as `extract_cookies.py` in your repo root. **Adjust the constants at
the top** for your OS/browser/profile:

```python
"""
extract_cookies.py
Extracts YouTube/Google cookies from a logged-in Chromium-based browser
profile and saves them in the {"cookies": [...], "origins": []} shape that
Steel.dev's sessionContext expects. Then pushes the result as a GitHub
Actions secret.

IMPORTANT: close the browser completely before running this — the cookie
database file is locked while the browser process is running.
"""
import base64, json, os, shutil, sqlite3, subprocess, sys
import win32crypt          # Windows only — swap for keyring/macOS Keychain APIs on other OSes
from Crypto.Cipher import AES

# ── EDIT THESE FOR YOUR SETUP ──────────────────────────────────────────────
PROFILE_DATA = r"C:\Users\<you>\AppData\Roaming\<Browser>\Browser Data\<profile-hash>"
REPO_DIR     = r"C:\path\to\my-channel-autoposter"
GITHUB_REPO  = "<your-username>/my-channel-autoposter"
# Set to True only if your browser adds a 32-byte prefix inside the decrypted
# payload (confirmed true for ixBrowser; Chrome itself does NOT do this —
# test with STRIP_PREFIX = False first, and if decrypted cookie values look
# like garbage/binary noise instead of readable text, flip it to True).
STRIP_PREFIX = False
# ─────────────────────────────────────────────────────────────────────────

LOCAL_STATE = os.path.join(PROFILE_DATA, "Local State")
COOKIES_SRC = os.path.join(PROFILE_DATA, "Default", "Network", "Cookies")
DB_COPY     = os.path.join(os.environ.get("TEMP", "/tmp"), "cookies_copy.db")


def get_aes_key():
    with open(LOCAL_STATE, encoding="utf-8") as f:
        ls = json.load(f)
    enc = base64.b64decode(ls["os_crypt"]["encrypted_key"])[5:]  # strip "DPAPI" header
    return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1]


def decrypt_cookie(key, ev):
    if ev[:3] in (b"v10", b"v20"):
        nonce, ct, tag = ev[3:15], ev[15:-16], ev[-16:]
        try:
            plain = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
            if STRIP_PREFIX:
                plain = plain[32:]
            return plain.decode("utf-8", errors="replace")
        except Exception:
            return None
    try:
        return win32crypt.CryptUnprotectData(ev, None, None, None, 0)[1].decode("utf-8", errors="replace")
    except Exception:
        return None


def main():
    if not os.path.exists(COOKIES_SRC):
        print(f"ERROR: Cookies not found at {COOKIES_SRC}")
        print("Is the path right, and is the browser fully closed?")
        sys.exit(1)

    shutil.copy2(COOKIES_SRC, DB_COPY)
    key = get_aes_key()

    conn = sqlite3.connect(DB_COPY)
    cur = conn.cursor()
    cur.execute("""
        SELECT host_key, path, name, encrypted_value, expires_utc, is_secure, is_httponly, samesite
        FROM cookies
        WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%google.com%'
        ORDER BY host_key, name
    """)
    rows = cur.fetchall()
    conn.close()

    samesite_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
    cookies = []
    for host_key, path, name, ev, expires_utc, is_secure, is_httponly, samesite in rows:
        value = decrypt_cookie(key, ev)
        if not value:
            continue
        unix_ts = (expires_utc / 1_000_000) - 11644473600 if expires_utc and expires_utc > 0 else None
        c = {
            "name": name, "value": value, "domain": host_key, "path": path,
            "httpOnly": bool(is_httponly), "secure": bool(is_secure),
            "sameSite": samesite_map.get(samesite, "Lax"),
        }
        if unix_ts and unix_ts > 0:
            c["expires"] = int(unix_ts)
        cookies.append(c)

    print(f"Decrypted {len(cookies)} cookies")
    if len(cookies) == 0:
        print("Zero cookies decrypted — you're likely hitting Chrome's App-Bound")
        print("Encryption (v127+). Switch to a different browser (see Option A above).")
        sys.exit(1)

    ctx = {"cookies": cookies, "origins": []}
    out = os.path.join(REPO_DIR, "data", "steel_context.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ctx, f, ensure_ascii=True, indent=2)
    print(f"Saved to {out}")

    with open(out, "rb") as f:
        result = subprocess.run(
            ["gh", "secret", "set", "STEEL_SESSION_CONTEXT", "--repo", GITHUB_REPO],
            stdin=f, capture_output=True, text=True,
        )
    if result.returncode == 0:
        print("SUCCESS: STEEL_SESSION_CONTEXT secret saved to GitHub!")
    else:
        print(f"gh secret set failed: {result.stderr}")
        print(f"Manual fallback: gh secret set STEEL_SESSION_CONTEXT --repo {GITHUB_REPO} < {out}")


if __name__ == "__main__":
    main()
```

**How to tell if `STRIP_PREFIX` should be `True`:** run the script with it
`False` first. If `data/steel_context.json` has cookie `value` fields that
look like readable session-token-like strings, you're done. If they look
like binary garbage / mojibake, set `STRIP_PREFIX = True` and rerun — some
Chromium forks (confirmed: ixBrowser) prepend a fixed 32-byte header inside
the AES-GCM plaintext that isn't part of the actual cookie value.

Run it:
```bash
python extract_cookies.py
```

---

## 4. Push the remaining secrets

```bash
gh secret set STEEL_API_KEY --repo <your-username>/my-channel-autoposter
# paste your Steel.dev API key when prompted

gh secret set YOUTUBE_CHANNEL_HANDLE --repo <your-username>/my-channel-autoposter
# paste your channel handle WITHOUT the @, e.g.:  mychannelname
```
(`STEEL_SESSION_CONTEXT` was already pushed by the script in step 3.)

---

## 5. Build your question bank

The posting script expects a JSON array where each item looks like this:

```json
{
  "id": "q0001",
  "question": "Your quiz question text here?",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "answer_index": 2,
  "explanations": [
    "Why Option A is right/wrong.",
    "Why Option B is right/wrong.",
    "Why Option C is right/wrong (this is the correct one, answer_index=2).",
    "Why Option D is right/wrong."
  ]
}
```

`explanations` is optional but strongly recommended — it's index-aligned
with `options`, and the posting script automatically fills YouTube's
"Explain why this is correct" field using it (see §8.6 for the platform
quirk around that field).

Generate this however suits your content — hardcode it, scrape it, use an
LLM, whatever. Save it as `data/content.json`. If you want more than one
category posted per run (like this repo's vocab + grammar split), create a
second file (e.g. `data/content_2.json`) and give it its own state-tracking
key (see §7).

Also create the tracking file:
```bash
echo '{"posted": []}' > data/state.json
```

---

## 6. The posting script

Save as `scripts/post_daily.py`:

```python
"""
post_daily.py
Posts the next unposted quiz question to a YouTube channel's Community tab
using a Steel.dev managed cloud browser + Playwright.

Env vars expected (set as GitHub Actions secrets):
  STEEL_API_KEY            - Steel.dev API key
  STEEL_SESSION_CONTEXT    - JSON cookie blob from extract_cookies.py
  YOUTUBE_CHANNEL_HANDLE   - channel handle WITHOUT the @
"""
import json, os, time
import requests
from playwright.sync_api import sync_playwright

STEEL_API_KEY = os.environ["STEEL_API_KEY"].replace('﻿', '').strip()
_ctx_raw = os.environ["STEEL_SESSION_CONTEXT"].replace('﻿', '').strip()
SESSION_CONTEXT = json.loads(_ctx_raw)
CHANNEL_HANDLE = os.environ["YOUTUBE_CHANNEL_HANDLE"].strip()
COMMUNITY_URL = f"https://www.youtube.com/@{CHANNEL_HANDLE}/community"

CONTENT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "content.json")
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")


def load_data():
    with open(CONTENT_FILE, encoding="utf-8") as f:
        questions = json.load(f)
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    state.setdefault("posted", [])
    return questions, state


def next_question(questions, posted_ids):
    posted = set(posted_ids)
    for q in questions:
        if q["id"] not in posted:
            return q
    print("All questions posted — resetting rotation.")
    posted_ids.clear()
    return questions[0]


def create_steel_session():
    for attempt in range(3):
        try:
            body = json.dumps({"sessionContext": SESSION_CONTEXT, "useProxy": False})
            r = requests.post(
                "https://api.steel.dev/v1/sessions",
                headers={"Steel-Api-Key": STEEL_API_KEY, "Content-Type": "application/json"},
                data=body.encode("utf-8"),   # NOT json= — avoids a latin-1 encoding crash if a BOM slips through
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
            session_id = data["id"]
            raw_ws = data.get("websocketUrl") or ""
            sep = "&" if "?" in raw_ws else "?"
            ws_url = raw_ws + f"{sep}apiKey={STEEL_API_KEY}"
            print(f"Steel session created: {session_id}")
            return session_id, ws_url
        except Exception as e:
            print(f"Session creation attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Failed to create Steel session after 3 attempts")


def release_steel_session(session_id):
    try:
        requests.delete(
            f"https://api.steel.dev/v1/sessions/{session_id}",
            headers={"Steel-Api-Key": STEEL_API_KEY}, timeout=30,
        )
    except Exception as e:
        print(f"Warning: could not release session: {e}")


def check_login(page):
    page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    state = page.evaluate("""(function() {
        var avatar = document.querySelector('#avatar-btn') || document.querySelector('yt-img-shadow#avatar');
        return { signedIn: !!avatar, title: document.title.substring(0, 60) };
    })()""")
    print(f"[login-check] {state}")


def post_quiz(page, question):
    page.goto(COMMUNITY_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)

    # Open composer, then the Quiz post type
    page.evaluate("""(function() {
        var b = Array.from(document.querySelectorAll('button'))
            .find(function(b) { return (b.textContent||'').trim() === "What's on your mind?"; });
        if (b) b.click();
    })()""")
    time.sleep(2)
    clicked_quiz = page.evaluate("""(function() {
        var b = Array.from(document.querySelectorAll('button'))
            .find(function(b) { return (b.textContent||'').trim() === 'Quiz'; });
        if (b) { b.click(); return true; }
        return false;
    })()""")
    print(f"[click-quiz-tab] {clicked_quiz}")
    time.sleep(2)

    q_text, options, ans_idx = question["question"], question["options"], question["answer_index"]

    # Question text
    filled_q = page.evaluate(f"""(function() {{
        var qField = document.querySelector('[contenteditable][placeholder*="community" i]') ||
                     document.querySelector('[contenteditable][placeholder*="ask" i]') ||
                     document.querySelector('[contenteditable][placeholder*="question" i]') ||
                     document.querySelector('#contenteditable-root');
        if (qField) {{
            qField.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, {json.dumps(q_text)});
            return true;
        }}
        return false;
    }})()""")
    print(f"[fill-question] {filled_q}")
    time.sleep(1)

    def visible_answer_textareas_js():
        return """
        function visibleAnswerTextareas() {
            return Array.from(document.querySelectorAll('textarea')).filter(function(t) {
                var p = (t.getAttribute('placeholder')||'').toLowerCase();
                if (!p.includes('answer')) return false;
                var r = t.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            });
        }"""

    # First two answers exist by default
    page.evaluate(f"""(function() {{
        {visible_answer_textareas_js()}
        var opts = {json.dumps(options)};
        var tas = visibleAnswerTextareas();
        for (var i = 0; i < Math.min(2, tas.length); i++) {{
            tas[i].focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, opts[i]);
        }}
    }})()""")
    time.sleep(1)

    # Add answers 3 & 4
    for extra_idx in range(2, 4):
        added = page.evaluate("""(function() {
            var btns = Array.from(document.querySelectorAll('button')).filter(function(b) {
                var r = b.getBoundingClientRect(); return r.width > 0 && r.height > 0;
            });
            var b = btns.find(function(b) { return (b.textContent||'').trim().toLowerCase() === 'add answer'; });
            if (b) { b.click(); return true; }
            return false;
        })()""")
        time.sleep(1.5)
        if added:
            page.evaluate(f"""(function() {{
                {visible_answer_textareas_js()}
                var opts = {json.dumps(options)};
                var tas = visibleAnswerTextareas();
                var t = tas[{extra_idx}];
                if (t) {{
                    t.focus();
                    document.execCommand('selectAll', false, null);
                    document.execCommand('insertText', false, opts[{extra_idx}]);
                }}
            }})()""")
            time.sleep(0.5)

    # Mark the correct answer — click the INNER <button>, not the [role=radio] wrapper
    page.evaluate(f"""(function() {{
        var radios = Array.from(document.querySelectorAll('[role="radio"]')).filter(function(r) {{
            var l = (r.getAttribute('aria-label')||'').toLowerCase();
            return l.includes('correct') || l.includes('mark');
        }});
        if (radios[{ans_idx}]) {{
            var target = radios[{ans_idx}].querySelector('button') || radios[{ans_idx}];
            target.click();
        }}
    }})()""")
    time.sleep(1)

    # Fill the explanation field — only the field for the CORRECT answer is visible/usable.
    # This field cannot render real line breaks (YouTube renders it with white-space:normal),
    # so use numbered prefixes instead of newlines if you want the paragraph to read as points.
    explanations = question.get("explanations")
    if explanations:
        numbered = [f"{i+1}) {exp}" for i, exp in enumerate(
            [explanations[ans_idx]] + [e for i, e in enumerate(explanations) if i != ans_idx]
        )]
        combined = numbered[0]
        for part in numbered[1:]:
            candidate = combined + " " + part
            if len(candidate) > 495:
                break
            combined = candidate
        visible_explain = page.locator('textarea[placeholder="Explain why this is correct (optional)"]').locator("visible=true")
        if visible_explain.count() > 0:
            try:
                visible_explain.first.fill(combined[:500], timeout=5000)
            except Exception as e:
                print(f"[fill-explanation] failed: {e}")

    page.evaluate("""(function(){document.activeElement.blur();})()""")
    time.sleep(0.5)

    # Wait for Post to actually be enabled before clicking
    post_enabled = False
    for _ in range(10):
        post_enabled = page.evaluate("""(function() {
            var b = Array.from(document.querySelectorAll('button')).find(
                function(b) { return (b.textContent||'').trim() === 'Post'; });
            return b ? !b.disabled : false;
        })()""")
        if post_enabled:
            break
        time.sleep(0.5)

    page.evaluate("""(function() {
        var b = Array.from(document.querySelectorAll('button')).find(function(b) {
            return (b.textContent||'').trim() === 'Post' && !b.disabled;
        });
        if (b) b.click();
    })()""")
    time.sleep(4)

    # Verify it actually submitted — composer resets to blank on success
    submitted = False
    for _ in range(6):
        root_text = page.evaluate("""(function() {
            var root = document.querySelector('#contenteditable-root');
            return root ? root.textContent.trim() : null;
        })()""")
        if not root_text:
            submitted = True
            break
        time.sleep(1)
    print(f"[submit-verify] submitted={submitted}")
    if not submitted:
        raise RuntimeError("Post did not submit — composer still shows unsent content after clicking Post")


def main():
    questions, state = load_data()
    question = next_question(questions, state["posted"])
    print(f"Next question: {question['id']} — {question['question']}")

    session_id, ws_url = create_steel_session()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(ws_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            check_login(page)
            post_quiz(page, question)

            state["posted"].append(question["id"])
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            print(f"State updated. Total posted: {len(state['posted'])}")

            browser.close()
    finally:
        release_steel_session(session_id)


if __name__ == "__main__":
    main()
```

> **Posting more than one category per run** (e.g. this repo's "vocab +
> grammar" split): duplicate the `load_data`/`next_question`/state-append
> block for a second content file with its own state key (e.g.
> `state["category_b_posted"]`), and call `post_quiz(page, ...)` a second
> time inside the same `with sync_playwright()` block — reuse the same
> `page` object, and only call `check_login()` once per run (calling it
> before every single post reintroduces a navigation-hang bug — see §8.2).

---

## 7. The GitHub Actions workflow

Save as `.github/workflows/post.yml`:

```yaml
name: Post Quiz

on:
  schedule:
    - cron: '13 * * * *'   # NOT '0 * * * *' — see §8.7 for why
  workflow_dispatch:        # lets you trigger it manually from the Actions tab

permissions:
  contents: write

jobs:
  post:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install playwright requests
          playwright install chromium

      - name: Post quiz question
        env:
          STEEL_API_KEY: ${{ secrets.STEEL_API_KEY }}
          STEEL_SESSION_CONTEXT: ${{ secrets.STEEL_SESSION_CONTEXT }}
          YOUTUBE_CHANNEL_HANDLE: ${{ secrets.YOUTUBE_CHANNEL_HANDLE }}
        run: python scripts/post_daily.py

      - name: Commit updated state
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/state.json
          git diff --cached --quiet || git commit -m "chore: update posted state [skip ci]"
          git push "https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/<your-username>/my-channel-autoposter.git"
```

Replace `<your-username>/my-channel-autoposter` with your actual repo path.

---

## 8. Commit, push, and test

```bash
git add .
git commit -m "Initial setup: automated quiz poster"
git push -u origin main   # or master, depending on your default branch
```

Trigger a manual test run before waiting for the cron:
```bash
gh workflow run post.yml --repo <your-username>/my-channel-autoposter
gh run watch --repo <your-username>/my-channel-autoposter
```

Check the run's logs for `[submit-verify] submitted=True`, then check the
channel's Community tab directly (use "Newest" sort — a brand-new post with
zero engagement can be buried by "Top"/popularity sort).

---

## 9. Gotcha checklist (things that will bite you if skipped)

1. **Chrome's App-Bound Encryption (v127+)** blocks cookie decryption
   entirely — use a different Chromium browser or manual export.
2. **BOM characters** (`﻿`) creep into secrets pushed from Windows —
   strip them from *every* secret you read in the script, including ones
   used in HTTP headers (a BOM there breaks `requests`'s latin-1 encoding).
3. **`git push` in Actions needs the token embedded in the URL** —
   `permissions: contents: write` alone isn't enough; a bare `git push`
   still 403s.
4. **Use `@handle/community`, not `channel/<ID>/community`** — the
   channel-ID URL returned a 404 for an authenticated session in testing.
5. **Use `domcontentloaded`, not `networkidle`**, for every navigation —
   YouTube keeps background connections open that make `networkidle` hang
   indefinitely, especially on a second navigation within the same session.
6. **Filter all form-field queries to visible elements** — YouTube's DOM
   contains hidden fields belonging to other post types (Poll, etc.) that a
   naive `querySelectorAll('textarea')` will also match.
7. **Click the inner `<button>`** inside `[role="radio"]` wrappers, not the
   wrapper element itself, when marking the correct answer.
8. **Mark the correct answer *before* touching the explanation field** —
   only the correct answer's explanation field is enabled; the other three
   are permanently `display:none` and cannot be filled.
9. **Use Playwright's `locator.fill()`**, not raw JS `element.value = ...`
   plus synthetic events — the framework's internal bound state silently
   discards synthetic-event updates on some fields.
10. **No newline trick renders as a real line break** in the explanation
    field (`\n`, Unicode U+2028, even genuine Enter keypresses — all
    collapsed by YouTube's own `white-space: normal` CSS). Use numbered
    prefixes (`"1) ... 2) ..."`) instead if you want the illusion of
    separate points.
11. **Poll for the Post button to be truly enabled** before clicking —
    `disabled=false` can lag slightly behind the framework's own validation.
12. **Verify the composer actually reset** after clicking Post, and raise an
    exception if it didn't — a clean script exit does *not* guarantee the
    post is actually live. Treat "no error was thrown" and "the content is
    live" as two separate claims that both need checking.
13. **Schedule cron jobs off the top of the hour** (`13 * * * *`, not
    `0 * * * *`) — GitHub explicitly documents `:00` as the most congested
    minute across all of Actions globally; scheduled runs at that exact
    minute are frequently delayed or silently dropped.

---

## 10. Ongoing maintenance

- **Cookie refresh**: session cookies eventually expire (typically weeks to
  months). If runs start failing at `check_login` or the composer never
  opens, close the source browser and rerun `python extract_cookies.py` to
  push a fresh `STEEL_SESSION_CONTEXT`.
- **Question bank refresh**: once `state.json`'s `posted` list reaches the
  length of your question bank, the rotation automatically wraps around and
  starts reposting from the top — add more questions to `data/content.json`
  whenever you want to extend the cycle before it repeats.
- **Monitoring**: `gh run list --repo <you>/<repo> --limit 20` from any
  machine shows recent run history without needing to open GitHub in a
  browser.
