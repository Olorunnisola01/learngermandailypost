"""
post_daily.py
Posts the next German vocabulary quiz question to the Learn German Without Stress
YouTube Community tab using Steel.dev managed browser + Playwright.

Env vars expected (set as GitHub secrets):
  STEEL_API_KEY           - Steel.dev API key
  STEEL_SESSION_CONTEXT   - JSON blob from extract_cookies.py (cookies)
  YOUTUBE_CHANNEL_ID      - UCZhxwaicihPtiQg-VAfN14A
"""
import json, os, sys, time
import requests
from playwright.sync_api import sync_playwright

STEEL_API_KEY   = os.environ["STEEL_API_KEY"]
# Strip BOM (﻿) that can appear when the secret was pushed from a Windows machine
_ctx_raw        = os.environ["STEEL_SESSION_CONTEXT"].lstrip('﻿').strip()
SESSION_CONTEXT = json.loads(_ctx_raw)
CHANNEL_ID      = os.environ.get("YOUTUBE_CHANNEL_ID", "UCZhxwaicihPtiQg-VAfN14A")
COMMUNITY_URL   = f"https://www.youtube.com/channel/{CHANNEL_ID}/community"

CONTENT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "content.json")
STATE_FILE   = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")


def load_data():
    with open(CONTENT_FILE, encoding="utf-8") as f:
        questions = json.load(f)
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {"posted": []}
    return questions, state


def next_question(questions, state):
    posted = set(state.get("posted", []))
    for q in questions:
        if q["id"] not in posted:
            return q
    # all posted — reset
    print("All questions posted, resetting state.")
    state["posted"] = []
    return questions[0]


def create_steel_session():
    for attempt in range(3):
        try:
            body = json.dumps({"sessionContext": SESSION_CONTEXT, "useProxy": False})
            r = requests.post(
                "https://api.steel.dev/v1/sessions",
                headers={"Steel-Api-Key": STEEL_API_KEY, "Content-Type": "application/json"},
                data=body.encode("utf-8"),
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
            session_id    = data["id"]
            ws_url        = data["websocketUrl"] + f"?apiKey={STEEL_API_KEY}"
            print(f"Steel session created: {session_id}")
            return session_id, ws_url
        except Exception as e:
            print(f"Session creation attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Failed to create Steel session after 3 attempts")


def release_steel_session(session_id):
    try:
        requests.delete(
            f"https://api.steel.dev/v1/sessions/{session_id}",
            headers={"Steel-Api-Key": STEEL_API_KEY},
            timeout=30,
        )
        print(f"Steel session {session_id} released.")
    except Exception as e:
        print(f"Warning: could not release session: {e}")


def post_quiz(page, question):
    """Navigate to Community tab and post a YouTube Quiz."""
    page.goto(COMMUNITY_URL, wait_until="networkidle", timeout=60000)
    time.sleep(3)

    # Click the "Create post" / text box area
    page.evaluate("""
        const box = document.querySelector('[placeholder*="community"]') ||
                    document.querySelector('[contenteditable="true"]');
        if (box) box.click();
    """)
    time.sleep(1)

    # Click "Poll / Quiz" button — look for the quiz icon in the post composer
    page.evaluate("""
        const btns = [...document.querySelectorAll('button, yt-icon-button, tp-yt-paper-button')];
        const quizBtn = btns.find(b => {
            const t = (b.textContent || b.getAttribute('aria-label') || '').toLowerCase();
            return t.includes('quiz') || t.includes('poll');
        });
        if (quizBtn) quizBtn.click();
    """)
    time.sleep(2)

    # Choose "Quiz" if a picker appeared
    page.evaluate("""
        const items = [...document.querySelectorAll('[role="menuitem"], [role="option"], button')];
        const quizItem = items.find(i => (i.textContent || '').trim().toLowerCase() === 'quiz');
        if (quizItem) quizItem.click();
    """)
    time.sleep(2)

    q_text   = question["question"]
    options  = question["options"]
    ans_idx  = question["answer_index"]

    # Fill question
    page.evaluate(f"""
        function deepQuery(root, sel) {{
            const res = [];
            const walk = (node) => {{
                try {{
                    node.querySelectorAll(sel).forEach(el => {{
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) res.push(el);
                    }});
                    node.querySelectorAll('*').forEach(c => {{ if (c.shadowRoot) walk(c.shadowRoot); }});
                }} catch(e) {{}}
            }};
            walk(root);
            return res;
        }}

        const qField = document.querySelector('[contenteditable][placeholder]') ||
                       deepQuery(document, '[contenteditable]')[0];
        if (qField) {{
            qField.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, {json.dumps(q_text)});
        }}
    """)
    time.sleep(1)

    # Fill answer options
    page.evaluate(f"""
        function deepQuery(root, sel) {{
            const res = [];
            const walk = (node) => {{
                try {{
                    node.querySelectorAll(sel).forEach(el => {{
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) res.push(el);
                    }});
                    node.querySelectorAll('*').forEach(c => {{ if (c.shadowRoot) walk(c.shadowRoot); }});
                }} catch(e) {{}}
            }};
            walk(root);
            return res;
        }}

        const options = {json.dumps(options)};
        const answerIdx = {ans_idx};

        // Get visible answer textareas
        let textareas = deepQuery(document, 'textarea[placeholder*="Answer"], textarea[placeholder*="answer"]');
        if (textareas.length === 0) {{
            textareas = deepQuery(document, 'textarea');
        }}

        // Fill first two (they already exist)
        for (let i = 0; i < Math.min(2, textareas.length); i++) {{
            textareas[i].focus();
            document.execCommand('insertText', false, options[i]);
        }}
    """)
    time.sleep(1)

    # Add answer 3 and 4 via "Add answer" button
    for extra_idx in range(2, 4):
        added = page.evaluate(f"""
            const btns = [...document.querySelectorAll('button')];
            const addBtn = btns.find(b => b.textContent.trim() === 'Add answer');
            if (addBtn) {{ addBtn.click(); true; }} else false;
        """)
        time.sleep(1)
        if added:
            page.evaluate(f"""
                function deepQuery(root, sel) {{
                    const res = [];
                    const walk = (node) => {{
                        try {{
                            node.querySelectorAll(sel).forEach(el => {{
                                const r = el.getBoundingClientRect();
                                if (r.width > 0 && r.height > 0) res.push(el);
                            }});
                            node.querySelectorAll('*').forEach(c => {{ if (c.shadowRoot) walk(c.shadowRoot); }});
                        }} catch(e) {{}}
                    }};
                    walk(root);
                    return res;
                }}
                const options = {json.dumps(options)};
                let textareas = deepQuery(document, 'textarea[placeholder*="Answer"], textarea[placeholder*="answer"]');
                if (textareas.length === 0) textareas = deepQuery(document, 'textarea');
                const t = textareas[{extra_idx}];
                if (t) {{
                    t.focus();
                    document.execCommand('insertText', false, options[{extra_idx}]);
                }}
            """)
            time.sleep(0.5)

    # Mark correct answer
    page.evaluate(f"""
        const correctBtns = [...document.querySelectorAll('[aria-label*="correct"], [aria-label*="Correct"]')];
        if (correctBtns[{ans_idx}]) correctBtns[{ans_idx}].click();
    """)
    time.sleep(1)

    # Click Post
    page.evaluate("""
        document.activeElement.blur();
    """)
    time.sleep(0.5)
    page.evaluate("""
        const postBtn = [...document.querySelectorAll('button')].find(
            b => b.textContent.trim() === 'Post' && !b.disabled
        );
        if (postBtn) postBtn.click();
    """)
    time.sleep(3)
    print(f"Posted: {q_text}")


def main():
    questions, state = load_data()
    question = next_question(questions, state)
    print(f"Next question: {question['id']} — {question['question']}")

    session_id, ws_url = create_steel_session()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(ws_url)
            ctx     = browser.contexts[0] if browser.contexts else browser.new_context()
            page    = ctx.pages[0] if ctx.pages else ctx.new_page()
            post_quiz(page, question)
            browser.close()
    finally:
        release_steel_session(session_id)

    # Update state
    state.setdefault("posted", []).append(question["id"])
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print(f"State updated. Total posted: {len(state['posted'])}")


if __name__ == "__main__":
    main()
