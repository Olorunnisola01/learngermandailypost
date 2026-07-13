# How the automated YouTube Community quiz poster works

This documents the full process behind this repo so it can be replicated for
other YouTube channels. It covers architecture, one-time setup, and the
gotchas discovered while building it.

## 1. Architecture overview

```
GitHub Actions (hourly cron)
   -> Steel.dev (cloud browser-as-a-service)
        -> Playwright connects over CDP to the Steel session
             -> Session is authenticated using cookies extracted once
                from a real logged-in browser profile
                  -> Navigates to youtube.com/@<handle>/community
                  -> Opens the Quiz composer, fills it, posts
   -> Commits updated "already posted" state back to the repo
```

No PC needs to be on. Everything runs on GitHub's servers, using Steel.dev as
a disposable cloud Chrome instance that replays your saved login cookies.

## 2. One-time setup per channel

### 2.1 Extract cookies from a real logged-in session

You need cookies from a browser profile that is already logged into the
target YouTube channel's Google account. Steel.dev accepts a `sessionContext`
(cookies + origins) at session-creation time to start "already logged in."

Key implementation details (see `extract_cookies.py`):

- Chrome 127+ uses "App-Bound Encryption" (v20) for cookie storage, which
  **cannot** be decrypted by a normal script — this blocked the original
  Chrome-based approach entirely (0 cookies extracted, no error).
- Fallback: use a different Chromium-based browser without app-bound
  encryption (e.g. ixBrowser) whose cookie store uses standard v10 AES-GCM,
  decryptable via `DPAPI` (Windows) + a fixed **32-byte prefix strip** after
  AES-GCM decryption (ixBrowser-specific quirk — Chrome doesn't need this
  strip, but ixBrowser does).
- Steps: copy `Cookies` sqlite DB from the profile's `Network` folder (while
  the browser is **closed**, to avoid file locks), decrypt each
  `encrypted_value` blob, filter to `*.youtube.com` / `*.google.com` domains,
  and write out `{"cookies": [...], "origins": []}` as JSON.
- Push that JSON as a GitHub Actions secret: `gh secret set STEEL_SESSION_CONTEXT < steel_context.json`.

**To replicate for another channel:** log into that channel's Google account
in a browser profile you can extract cookies from, then rerun the extraction
script pointed at that profile's cookie DB.

### 2.2 GitHub repo secrets required

| Secret | Purpose |
|---|---|
| `STEEL_API_KEY` | Steel.dev API key |
| `STEEL_SESSION_CONTEXT` | The cookie JSON from step 2.1 |
| `YOUTUBE_CHANNEL_ID` | Not strictly used for navigation (we use the handle URL instead) but kept for reference |
| `GITHUB_TOKEN` | Auto-provided by Actions; used to let the workflow push its own commits |

### 2.3 Repo permissions

`.github/workflows/*.yml` needs:
```yaml
permissions:
  contents: write
```
and the final commit step must push using the token explicitly:
```yaml
git push "https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/<owner>/<repo>.git"
```
(A bare `git push` fails with 403 — the default `GITHUB_TOKEN` isn't wired
into the local git credential helper automatically.)

## 3. Question bank generation

Two static JSON files are generated **once**, ahead of time (not per-post):
- `data/content.json` — vocabulary quiz questions (word → 4 options)
- `data/grammar.json` — grammar fill-in-the-blank questions (verb
  conjugation, article/gender, pronoun agreement, adjective endings,
  prepositions, conjunctions)

Each question object looks like:
```json
{
  "id": "v0001",
  "question": "What is the German word for 'banana'?",
  "options": ["die Banane", "die Kellertür", "das Haus", "das Sportzentrum"],
  "answer_index": 0,
  "explanations": [
    "'die Banane' is correct — it is the German word for 'banana'.",
    "'die Kellertür' is incorrect — it means 'cellar door', not 'banana'.",
    "...",
    "..."
  ]
}
```
`explanations` is index-aligned with `options`. For grammar questions each
explanation also includes an English meaning gloss first (e.g. `"'Halbkugel'
means 'hemisphere'. 'die' is correct — ..."`) so the quiz is usable by someone
with zero prior vocabulary knowledge.

`data/state.json` tracks which question IDs have already been posted per
category (`vocab_posted`, `grammar_posted`), so the rotation never repeats
until the whole bank is exhausted, then wraps around.

**To replicate:** swap in your own question-generation logic (or hand-written
question banks) in the same `{question, options, answer_index, explanations}`
shape — the posting script doesn't care how the JSON was produced.

## 4. The posting script (`scripts/post_daily.py`)

### 4.1 Session lifecycle
```python
session_id, ws_url = create_steel_session()   # POST /v1/sessions with sessionContext
browser = playwright.chromium.connect_over_cdp(ws_url)
...
release_steel_session(session_id)             # DELETE the session when done
```

### 4.2 Navigating
Use the **handle URL**, not the channel-ID URL:
```
https://www.youtube.com/@<handle>/community
```
`youtube.com/channel/<ID>/community` returned a 404 for the authenticated
session in testing — the handle URL is the reliable one.

Use `wait_until="domcontentloaded"`, not `"networkidle"`. YouTube keeps
persistent background connections open (notifications, live chat polling)
that mean `networkidle` never resolves — it will hang and time out,
especially on the *second* navigation within the same page/session.

### 4.3 Opening the Quiz composer
1. Click the "What's on your mind?" placeholder button to expand the composer.
2. Click the "Quiz" button in the row of post-type icons (Image / Image poll
   / Text poll / Video / Quiz).
3. Fill the question text into the `#contenteditable-root` div (fall back
   through a few placeholder-based selectors first, since the exact
   `aria-label`/`placeholder` text can vary).

### 4.4 Filling answers — the visibility trap
YouTube reuses hidden poll-type "Option 1/2" fields in the same DOM even when
you're composing a Quiz. Naively querying all `<textarea>` elements picks up
these **hidden** poll fields too. Fix: filter to elements with
`getBoundingClientRect().width > 0 && height > 0` (visible), and match on
`placeholder` containing `"Answer"` specifically (not `"Option"`).

Only 2 answer fields exist by default; click "Add answer" twice to reveal
slots 3 and 4, waiting ~1.5s after each click for the new field to render
before trying to fill it.

### 4.5 Marking the correct answer
The clickable target is **not** the `[role="radio"]` element itself — it's
the `<button>` nested one level inside it:
```js
var target = radios[ans_idx].querySelector('button') || radios[ans_idx];
target.click();
```
Verify with `radios[ans_idx].getAttribute('aria-checked') === "true"` after
clicking, and retry once if it didn't register.

### 4.6 The "Explain why this is correct" field — key limitation
YouTube's quiz UI has an explanation field per answer, but **only the field
belonging to whichever answer is currently marked correct is enabled/visible**
— the other three are permanently `display:none` in the DOM (they exist, but
can't be filled or read). This means:
- **Mark the correct answer *before* trying to fill any explanation field.**
- Only fill the **one** now-visible field
  (`textarea[placeholder="Explain why this is correct (optional)"]`,
  filtered to `visible=true`), using Playwright's `locator.fill(...)` — plain
  JS `.value =` + synthetic `input`/`change` events do **not** stick (the
  framework's bound state silently discards them).
- This field is capped at 500 characters and renders with `white-space:
  normal` in YouTube's own CSS — **no newline character (plain `\n`, Unicode
  U+2028 Line Separator, or even a real Enter keypress) produces a visible
  line break.** If you want the illusion of multiple points, use a
  separator like `"1) ... 2) ... 3) ..."` inside the single string; true
  multi-line formatting isn't achievable here — this is a platform
  constraint, not a scripting workaround away from.
- Since only one option's explanation is visible, combine "why correct" +
  condensed "why the others are wrong" into that single field, trimming to
  fit under 500 chars (drop lowest-priority items first if it doesn't fit).

### 4.7 Clicking Post — wait for it to actually be enabled
The Post button can report `disabled=false` in the DOM slightly before the
framework's internal validation has caught up. Poll up to ~5s for
`!button.disabled` to be true before clicking, rather than clicking on the
first check.

### 4.8 Verifying the post actually went through
After clicking Post, the composer resets to its blank/placeholder state on
success. Poll for `#contenteditable-root` to be empty; if it never empties
within a few seconds, **raise an exception** rather than assuming success —
early versions of this script logged "Post clicked" and reported success even
when the click silently no-opped (e.g. because the button was still
disabled), leading to state being marked posted when nothing was actually
live. Treat "the workflow step didn't error" and "the content is actually
live" as two different claims that both need verification.

## 5. Scheduling

```yaml
on:
  schedule:
    - cron: '13 * * * *'   # NOT '0 * * * *'
  workflow_dispatch:
```
GitHub explicitly documents that `:00` (top of every hour) is the most
congested minute across all of GitHub Actions globally — scheduled runs at
that exact minute are frequently delayed or silently dropped under load. Pick
any other minute (`:07`, `:13`, `:42`, whatever) to get reliable hourly
firing.

**Symptom if you hit this**: `gh run list --json event | jq 'select(.event=="schedule")'`
shows far fewer scheduled runs than hours elapsed, with no error — they just
never fired.

## 6. Running two post types per cron tick

Rather than run the workflow twice an hour, `main()` in `post_daily.py`
posts a vocab question **and** a grammar question sequentially within the
same Steel session/browser page, each with its own state-tracking list. Only
call `check_login()` (which navigates to `youtube.com` and checks the
avatar/sign-in state) **once** per run — calling it before every post
reintroduces the `networkidle` hang problem from 4.2.

## 7. Full gotcha checklist (for fast replication)

1. Chrome's cookie encryption blocks extraction on modern versions — use an
   alternate browser or accept manual cookie copy.
2. GitHub secrets pushed from Windows can carry a BOM (`﻿`) — strip it
   with `.replace('﻿', '').strip()` before `json.loads`, on **every**
   secret you read, including API keys used in HTTP headers (a BOM in a
   header value breaks the underlying latin-1 encoding `requests` uses).
3. `git push` in Actions needs the explicit token-embedded URL, plus
   `permissions: contents: write` in the workflow.
4. Use the `@handle/community` URL, not `channel/<ID>/community`.
5. Use `domcontentloaded`, not `networkidle`, for all YouTube navigations.
6. Filter all form-field queries to **visible** elements — YouTube's DOM
   contains hidden fields for other post types.
7. Click the inner `<button>` of `[role="radio"]` wrappers, not the wrapper.
8. Mark the correct answer **before** touching the explanation field.
9. Use Playwright's `locator.fill()`, not raw JS value-setting, for anything
   whose value needs to survive to submission.
10. No newline trick works in the explanation field — use numbered prefixes.
11. Poll for the Post button to be truly enabled before clicking.
12. Verify the composer actually reset after clicking Post — don't trust a
    clean exit code alone.
13. Schedule cron jobs off the top of the hour.
