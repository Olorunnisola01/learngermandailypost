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

STEEL_API_KEY   = os.environ["STEEL_API_KEY"].replace('﻿', '').strip()
# Strip BOM (﻿) that appears when the secret was pushed from a Windows machine
_ctx_raw        = os.environ["STEEL_SESSION_CONTEXT"].replace('﻿', '').strip()
print(f"[debug] ctx_raw first 40 chars: {repr(_ctx_raw[:40])}")
print(f"[debug] API key first char ord: {ord(STEEL_API_KEY[0]) if STEEL_API_KEY else 'empty'}")
SESSION_CONTEXT = json.loads(_ctx_raw)
CHANNEL_ID      = os.environ.get("YOUTUBE_CHANNEL_ID", "UCZhxwaicihPtiQg-VAfN14A")
COMMUNITY_URL   = "https://www.youtube.com/@learngermanwithoutstress/community"

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
            print(f"[debug] Steel API response keys: {list(data.keys())}")
            print(f"[debug] session id: {data.get('id','MISSING')}")
            print(f"[debug] websocketUrl raw: {data.get('websocketUrl','MISSING')}")
            session_id    = data["id"]
            raw_ws        = data.get("websocketUrl") or ""
            # Append apiKey using & if URL already has query params, else ?
            sep = "&" if "?" in raw_ws else "?"
            ws_url        = raw_ws + f"{sep}apiKey={STEEL_API_KEY}"
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


def page_dump(page, label):
    info = page.evaluate("""(function() {
        var btns = Array.from(document.querySelectorAll('button')).slice(0,30).map(function(b){
            return (b.textContent||'').trim().substring(0,60);
        }).filter(function(t){return t.length>0;});
        var inputs = Array.from(document.querySelectorAll('[contenteditable],[placeholder],textarea')).slice(0,10).map(function(el){
            return el.tagName+'['+(el.getAttribute('placeholder')||el.getAttribute('aria-label')||'')+']';
        });
        return {title:document.title, url:location.href, btns:btns, inputs:inputs};
    })()""")
    print(f"[{label}] title={info['title'][:80]}")
    print(f"[{label}] url={info['url'][:120]}")
    print(f"[{label}] btns={info['btns']}")
    print(f"[{label}] inputs={info['inputs']}")


def post_quiz(page, question):
    """Navigate to Community tab and post a YouTube Quiz."""
    # First go to youtube.com to check login state before hitting community tab
    page.goto("https://www.youtube.com", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    login_state = page.evaluate("""(function() {
        // Check for avatar/account button (logged in) vs Sign In button
        var signIn = document.querySelector('[aria-label="Sign in"]');
        var avatar = document.querySelector('#avatar-btn') || document.querySelector('yt-img-shadow#avatar');
        return {signedIn: !!avatar, signInBtnFound: !!signIn, title: document.title.substring(0,60)};
    })()""")
    print(f"[login-check] {login_state}")

    page.goto(COMMUNITY_URL, wait_until="networkidle", timeout=60000)
    time.sleep(4)
    page_dump(page, "after-goto")

    # Click the "Create post" text box area to open composer
    clicked_box = page.evaluate("""(function() {
        var sels = ['#placeholder-area','#contenteditable-root','[contenteditable="true"]',
                    '[placeholder*="community" i]','[placeholder*="post" i]'];
        for (var i=0;i<sels.length;i++){
            var el=document.querySelector(sels[i]);
            if(el){el.click();return sels[i];}
        }
        return null;
    })()""")
    print(f"[click-box] {clicked_box}")
    time.sleep(2)
    page_dump(page, "after-click-box")

    # Click "Poll / Quiz" button to open post-type picker
    clicked_poll = page.evaluate("""(function() {
        var all = Array.from(document.querySelectorAll('button,yt-icon-button,tp-yt-paper-button'));
        var labels = ['quiz','poll'];
        for (var i=0;i<all.length;i++){
            var t=((all[i].textContent||'')+(all[i].getAttribute('aria-label')||'')).toLowerCase();
            for(var j=0;j<labels.length;j++){if(t.includes(labels[j])){all[i].click();return t;}}
        }
        return null;
    })()""")
    print(f"[click-poll] {clicked_poll}")
    time.sleep(2)
    page_dump(page, "after-click-poll")

    # Pick "Quiz" from menu if it appeared
    clicked_quiz = page.evaluate("""(function() {
        var items = Array.from(document.querySelectorAll(
            '[role="menuitem"],[role="option"],paper-item,ytd-menu-service-item-renderer'));
        for(var i=0;i<items.length;i++){
            var t=(items[i].textContent||'').trim().toLowerCase();
            if(t==='quiz'||t.includes('quiz')){items[i].click();return t;}
        }
        return null;
    })()""")
    print(f"[click-quiz-item] {clicked_quiz}")
    time.sleep(2)
    page_dump(page, "after-quiz-picker")

    q_text   = question["question"]
    options  = question["options"]
    ans_idx  = question["answer_index"]

    def deep_query_js():
        return """
        function deepQuery(root, sel) {
            var res = [];
            function walk(node) {
                try {
                    node.querySelectorAll(sel).forEach(function(el) {
                        var r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) res.push(el);
                    });
                    node.querySelectorAll('*').forEach(function(c) { if (c.shadowRoot) walk(c.shadowRoot); });
                } catch(e) {}
            }
            walk(root);
            return res;
        }"""

    # Fill question field
    filled_q = page.evaluate(f"""(function() {{
        {deep_query_js()}
        var candidates = [
            document.querySelector('#question-input textarea'),
            document.querySelector('[placeholder*="question" i]'),
            deepQuery(document,'textarea')[0],
            document.querySelector('[contenteditable][placeholder]'),
            deepQuery(document,'[contenteditable]')[0],
        ];
        for(var i=0;i<candidates.length;i++){{
            var el=candidates[i];
            if(el){{
                el.focus();
                document.execCommand('selectAll',false,null);
                document.execCommand('insertText',false,{json.dumps(q_text)});
                return el.tagName+'['+(el.getAttribute('placeholder')||'')+']';
            }}
        }}
        return null;
    }})()""")
    print(f"[fill-question] {filled_q}")
    time.sleep(1)
    page_dump(page, "after-fill-question")

    # Fill first two answer options
    filled_opts = page.evaluate(f"""(function() {{
        {deep_query_js()}
        var opts = {json.dumps(options)};
        var textareas = deepQuery(document,'textarea[placeholder*="Answer" i]');
        if(textareas.length===0) textareas=deepQuery(document,'textarea');
        var filled=[];
        for(var i=0;i<Math.min(2,textareas.length);i++){{
            textareas[i].focus();
            document.execCommand('selectAll',false,null);
            document.execCommand('insertText',false,opts[i]);
            filled.push(opts[i]);
        }}
        return filled;
    }})()""")
    print(f"[fill-opts-1-2] {filled_opts}")
    time.sleep(1)

    # Add option 3 and 4
    for extra_idx in range(2, 4):
        added = page.evaluate("""(function() {
            var btns=Array.from(document.querySelectorAll('button'));
            var b=btns.find(function(b){
                var t=(b.textContent||'').trim().toLowerCase();
                return t==='add answer'||t==='add option'||t.includes('add answer');
            });
            if(b){b.click();return b.textContent.trim();} return null;
        })()""")
        print(f"[add-answer-btn-{extra_idx}] {added}")
        time.sleep(1)
        if added:
            filled = page.evaluate(f"""(function() {{
                {deep_query_js()}
                var opts={json.dumps(options)};
                var tas=deepQuery(document,'textarea[placeholder*="Answer" i]');
                if(tas.length===0) tas=deepQuery(document,'textarea');
                var t=tas[{extra_idx}];
                if(t){{t.focus();document.execCommand('selectAll',false,null);
                       document.execCommand('insertText',false,opts[{extra_idx}]);return opts[{extra_idx}];}}
                return null;
            }})()""")
            print(f"[fill-opt-{extra_idx}] {filled}")
            time.sleep(0.5)

    # Mark correct answer
    marked = page.evaluate(f"""(function() {{
        var btns=Array.from(document.querySelectorAll('button,[role="radio"],[role="checkbox"]'));
        var correct=btns.filter(function(b){{
            var l=(b.getAttribute('aria-label')||b.getAttribute('title')||'').toLowerCase();
            return l.includes('correct')||l.includes('mark')||l.includes('answer');
        }});
        console.log('correct btns:',correct.length,correct.map(function(b){{return b.getAttribute('aria-label');}}));
        if(correct[{ans_idx}]){{correct[{ans_idx}].click();return correct[{ans_idx}].getAttribute('aria-label');}}
        return 'none found (count='+correct.length+')';
    }})()""")
    print(f"[mark-correct] {marked}")
    time.sleep(1)
    page_dump(page, "before-post")

    # Click Post button
    page.evaluate("""(function(){document.activeElement.blur();})()""")
    time.sleep(0.5)
    clicked_post = page.evaluate("""(function() {
        var btns=Array.from(document.querySelectorAll('button,ytd-button-renderer,tp-yt-paper-button'));
        var b=btns.find(function(b){
            var t=(b.textContent||'').trim();
            return (t==='Post'||t==='post')&&!b.disabled;
        });
        if(b){b.click();return 'Post btn clicked';}
        var b2=btns.find(function(b){return (b.getAttribute('aria-label')||'').toLowerCase()==='post';});
        if(b2){b2.click();return 'aria-label=post clicked';}
        return null;
    })()""")
    print(f"[click-post] {clicked_post}")
    time.sleep(4)
    page_dump(page, "after-post")


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
