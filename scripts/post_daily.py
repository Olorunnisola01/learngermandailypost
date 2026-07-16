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



GRAMMAR_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "grammar.json")



STATE_FILE   = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")











def load_data():



    with open(CONTENT_FILE, encoding="utf-8") as f:



        vocab_questions = json.load(f)



    with open(GRAMMAR_FILE, encoding="utf-8") as f:



        grammar_questions = json.load(f)



    try:



        with open(STATE_FILE, encoding="utf-8") as f:



            state = json.load(f)



    except FileNotFoundError:



        state = {}



    # Migrate legacy state format {"posted": [...]}  ->  {"vocab_posted": [...]}



    if "posted" in state and "vocab_posted" not in state:



        state["vocab_posted"] = state.pop("posted")



    state.setdefault("vocab_posted", [])



    state.setdefault("grammar_posted", [])



    return vocab_questions, grammar_questions, state











def next_question(questions, posted_ids, label):



    posted = set(posted_ids)



    for q in questions:



        if q["id"] not in posted:



            return q



    print(f"All {label} questions posted, resetting.")



    posted_ids.clear()



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











def check_login(page):



    page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=60000)



    time.sleep(3)



    login_state = page.evaluate("""(function() {



        var signIn = document.querySelector('[aria-label="Sign in"]');



        var avatar = document.querySelector('#avatar-btn') || document.querySelector('yt-img-shadow#avatar');



        return {signedIn: !!avatar, signInBtnFound: !!signIn, title: document.title.substring(0,60)};



    })()""")



    print(f"[login-check] {login_state}")











def post_quiz(page, question):



    """Navigate to Community tab and post a YouTube Quiz."""



    page.goto(COMMUNITY_URL, wait_until="domcontentloaded", timeout=60000)



    time.sleep(4)



    page_dump(page, "after-goto")







    # Step 1a: Expand the community composer
    page.evaluate("""(function(){
        var el = document.querySelector('#contenteditable-root') ||
                 document.querySelector('[placeholder]');
        if(el){ el.click(); el.focus(); }
    })()""")
    print("[expand-composer] done")
    time.sleep(3)

    # Step 1b: Click Quiz tab using Playwright locators (pierce shadow DOM)
    clicked_quiz = None

    # Try 1: Playwright text locator — pierces shadow DOM
    try:
        quiz_locator = page.get_by_text("Quiz", exact=True)
        count = quiz_locator.count()
        print(f"[quiz-playwright-count] {count}")
        if count > 0:
            for i in range(count):
                try:
                    el = quiz_locator.nth(i)
                    if el.is_visible(timeout=1000):
                        el.click(timeout=3000)
                        clicked_quiz = f"playwright nth={i}"
                        break
                except Exception:
                    pass
    except Exception as e:
        print(f"[quiz-playwright-err] {e}")

    # Try 2: role=tab with name Quiz
    if not clicked_quiz:
        try:
            tab = page.get_by_role("tab", name="Quiz")
            if tab.count() > 0 and tab.first.is_visible(timeout=1000):
                tab.first.click(timeout=3000)
                clicked_quiz = "playwright-role-tab"
        except Exception as e:
            print(f"[quiz-role-tab-err] {e}")

    # Try 3: paper-tab element containing Quiz text
    if not clicked_quiz:
        try:
            el = page.locator("tp-yt-paper-tab:has-text('Quiz')")
            if el.count() > 0 and el.first.is_visible(timeout=1000):
                el.first.click(timeout=3000)
                clicked_quiz = "playwright-paper-tab"
        except Exception as e:
            print(f"[quiz-paper-tab-err] {e}")

    # Try 4: JavaScript deep shadow DOM search
    if not clicked_quiz:
        result = page.evaluate("""(function(){
            function dQ(root, sel){
                var r=Array.from(root.querySelectorAll(sel));
                Array.from(root.querySelectorAll('*')).forEach(function(e){
                    if(e.shadowRoot) r=r.concat(dQ(e.shadowRoot,sel));
                });
                return r;
            }
            function dText(root,pat){
                var found=[];
                Array.from(root.querySelectorAll('*')).forEach(function(el){
                    var t=Array.from(el.childNodes).filter(function(n){return n.nodeType===3;}).map(function(n){return n.textContent;}).join('');
                    if(pat.test(t.trim())) found.push(el);
                    if(el.shadowRoot) found=found.concat(dText(el.shadowRoot,pat));
                });
                return found;
            }
            var all=dQ(document,'button,[role="tab"],tp-yt-paper-tab,[role="button"]');
            var info=all.filter(function(el){var r=el.getBoundingClientRect();return r.width>0&&r.height>0;}).map(function(el){return (el.textContent||'').trim().substring(0,25)+'|'+(el.getAttribute('aria-label')||'');}).filter(function(s){return s.trim().length>1;});
            var byText=dText(document,/^quiz$/i);
            if(byText.length>0){
                var t=byText[0].closest('[role="tab"],button,[tabindex]')||byText[0];
                t.click();
                return 'deep-text:'+t.tagName;
            }
            var byLabel=dQ(document,'[aria-label*="quiz" i]');
            if(byLabel.length>0){byLabel[0].click();return 'deep-label:'+byLabel[0].getAttribute('aria-label');}
            return 'not-found|interactive='+JSON.stringify(info.slice(0,25));
        })()""")
        print(f"[quiz-js-deep] {result}")
        if "deep-text" in str(result) or "deep-label" in str(result):
            clicked_quiz = f"js-deep: {result}"

    print(f"[click-quiz-tab] {clicked_quiz}")
    time.sleep(2)
    page_dump(page, "after-quiz-tab")







    q_text  = question["question"]



    options = question["options"]



    ans_idx = question["answer_index"]







    # Step 2: Fill the question field (the community ask box, NOT the search bar)



    # After clicking Quiz tab, the question field is a contenteditable div with placeholder



    # "Ask your community..." or similar — we target it by placeholder, avoiding the search textarea



    filled_q = page.evaluate(f"""(function() {{



        // Target the community post contenteditable, not the search bar



        var qField = document.querySelector('[contenteditable][placeholder*="community" i]') ||



                     document.querySelector('[contenteditable][placeholder*="ask" i]') ||



                     document.querySelector('[contenteditable][placeholder*="question" i]') ||



                     document.querySelector('#contenteditable-root');



        if (qField) {{



            qField.focus();



            document.execCommand('selectAll', false, null);



            document.execCommand('insertText', false, {json.dumps(q_text)});



            return 'filled: ' + qField.tagName + '[' + (qField.getAttribute('placeholder')||'') + ']';



        }}



        return 'question field not found';



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







    # Step 3: Fill answer options — target visible TEXTAREA[Answer N] (not hidden poll Option fields)



    filled_opts = page.evaluate(f"""(function() {{



        {visible_answer_textareas_js()}



        var opts = {json.dumps(options)};



        var tas = visibleAnswerTextareas();



        var filled = [];



        for (var i = 0; i < Math.min(2, tas.length); i++) {{



            tas[i].focus();



            document.execCommand('selectAll', false, null);



            document.execCommand('insertText', false, opts[i]);



            filled.push(opts[i]);



        }}



        return filled;



    }})()""")



    print(f"[fill-opts-1-2] {filled_opts}")



    time.sleep(1)







    # Step 4: Add options 3 and 4 via the visible "Add answer" button



    for extra_idx in range(2, 4):



        added = page.evaluate("""(function() {



            var btns = Array.from(document.querySelectorAll('button')).filter(function(b) {



                var r = b.getBoundingClientRect();



                return r.width > 0 && r.height > 0;



            });



            var b = btns.find(function(b) { return (b.textContent||'').trim().toLowerCase() === 'add answer'; });



            if (!b) b = btns.find(function(b) { return (b.textContent||'').trim().toLowerCase() === 'add option'; });



            if (b) { b.click(); return b.textContent.trim(); }



            return null;



        })()""")



        print(f"[add-answer-{extra_idx}] {added}")



        time.sleep(1.5)



        if added:



            filled = page.evaluate(f"""(function() {{



                {visible_answer_textareas_js()}



                var opts = {json.dumps(options)};



                var tas = visibleAnswerTextareas();



                var t = tas[{extra_idx}];



                if (t) {{



                    t.focus();



                    document.execCommand('selectAll', false, null);



                    document.execCommand('insertText', false, opts[{extra_idx}]);



                    return opts[{extra_idx}];



                }}



                return 'textarea not found (count='+tas.length+')';



            }})()""")



            print(f"[fill-opt-{extra_idx}] {filled}")



            time.sleep(0.5)







    # Step 5: Mark the correct answer using aria-label (confirmed working selector)



    marked = page.evaluate(f"""(function() {{



        var btns = Array.from(document.querySelectorAll('[aria-label="Mark as correct answer"]'));



        if (btns[{ans_idx}]) {{



            btns[{ans_idx}].click();



            return 'clicked Mark-as-correct btn ' + {ans_idx} + ' of ' + btns.length;



        }}



        return 'btn not found (count=' + btns.length + ')';



    }})()""")



    print(f"[mark-correct] {marked}")



    time.sleep(1)







    # Verify the button was found; retry once if not found yet



    checked = page.evaluate(f"""(function() {{



        var btns = Array.from(document.querySelectorAll('[aria-label="Mark as correct answer"]'));



        return 'btn-count=' + btns.length + (btns[{ans_idx}] ? ' found' : ' missing');



    }})()""")



    print(f"[mark-correct-verify] aria-checked={checked}")



    if checked != "true":



        page.evaluate(f"""(function() {{



            var btns = Array.from(document.querySelectorAll('[aria-label="Mark as correct answer"]'));



            if (btns[{ans_idx}]) btns[{ans_idx}].click();



        }})()""")



        time.sleep(1)







    # Step 5b: Fill the "Explain why this is correct" field — YouTube only reveals/keeps ONE such



    # field, for whichever answer is marked correct (it's display:none for the other 3 until then).



    # This field renders with white-space:normal (YouTube's own CSS) which collapses ANY newline —



    # plain "\n", U+2028, even a real Enter keypress — into a single space, so true separate rows



    # aren't achievable here. Use numbered prefixes instead so the text still reads as distinct,



    # scannable points within the single paragraph YouTube renders.



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







        explain_locator = page.locator('textarea[placeholder="Explain why this is correct (optional)"]')



        visible_explain = explain_locator.locator("visible=true")



        vcount = visible_explain.count()



        filled_explain = "none"



        if vcount > 0:



            try:



                visible_explain.first.fill(combined[:500], timeout=5000)



                filled_explain = "ok"



            except Exception as e:



                filled_explain = f"failed: {e}"



        print(f"[fill-explanation] visible_count={vcount} result={filled_explain}")







    page_dump(page, "before-post")







    # Step 6: Wait for Post button to be enabled (poll up to 5s), then click



    page.evaluate("""(function(){document.activeElement.blur();})()""")



    time.sleep(0.5)



    post_enabled = False



    for _ in range(10):



        post_enabled = page.evaluate("""(function() {



            var btns = Array.from(document.querySelectorAll('button'));



            var b = btns.find(function(b) { return (b.textContent||'').trim() === 'Post'; });



            return b ? !b.disabled : false;



        })()""")



        if post_enabled:



            break



        time.sleep(0.5)



    print(f"[post-button-enabled] {post_enabled}")







    clicked_post = page.evaluate("""(function() {



        var btns = Array.from(document.querySelectorAll('button'));



        var b = btns.find(function(b) {



            var t = (b.textContent||'').trim();



            return t === 'Post' && !b.disabled;



        });



        if (b) { b.click(); return 'Post clicked'; }



        return 'Post button not found or still disabled';



    })()""")



    print(f"[click-post] {clicked_post}")



    time.sleep(4)



    page_dump(page, "after-post")







    # Step 7: Verify submission — the composer resets to its blank/placeholder state on success



    submitted = False



    for _ in range(6):



        reset_state = page.evaluate("""(function() {



            var root = document.querySelector('#contenteditable-root');



            var text = root ? root.textContent.trim() : null;



            return { rootText: text };



        })()""")



        if not reset_state["rootText"]:



            submitted = True



            break



        time.sleep(1)



    print(f"[submit-verify] submitted={submitted}")



    if not submitted:



        raise RuntimeError("Post did not submit — composer still shows unsent content after clicking Post")











def main():



    vocab_questions, grammar_questions, state = load_data()



    vocab_q   = next_question(vocab_questions, state["vocab_posted"], "vocab")



    grammar_q = next_question(grammar_questions, state["grammar_posted"], "grammar")



    print(f"Next vocab question: {vocab_q['id']} — {vocab_q['question']}")



    print(f"Next grammar question: {grammar_q['id']} — {grammar_q['question']}")







    session_id, ws_url = create_steel_session()



    try:



        with sync_playwright() as pw:



            browser = pw.chromium.connect_over_cdp(ws_url)



            ctx     = browser.contexts[0] if browser.contexts else browser.new_context()



            page    = ctx.pages[0] if ctx.pages else ctx.new_page()







            check_login(page)







            post_quiz(page, vocab_q)



            state["vocab_posted"].append(vocab_q["id"])



            with open(STATE_FILE, "w", encoding="utf-8") as f:



                json.dump(state, f, indent=2)



            print(f"Vocab state saved. Total posted: {len(state['vocab_posted'])}")







            post_quiz(page, grammar_q)



            state["grammar_posted"].append(grammar_q["id"])



            with open(STATE_FILE, "w", encoding="utf-8") as f:



                json.dump(state, f, indent=2)



            print(f"Grammar state saved. Total posted: {len(state['grammar_posted'])}")







            browser.close()



    finally:



        release_steel_session(session_id)











if __name__ == "__main__":



    main()







