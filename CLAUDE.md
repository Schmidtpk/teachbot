# Lectos

## Context

I am a university professor in economics working on decision theory, microeconomics, and forecast evaluation.
For my lectures, and other educators, I want to build an open-source tool that sets up an online chat environment for students, where an LLM API is used for interactions that are enriched by the lecture content. The key functionality should be

- **QA**: Ask questions the chatbot answers based on lecture content
- **Learn**: Chatbot explains and makes test questions with Socratic dialogue to teach students a certain topic
- **Eval**: Chatbot evaluates chat and gives qualitative feedback and grade to student

All interactions should have a simple feedback mechanism, where students can immediately give feedback to the lecturer if something went wrong or the agent misbehaves/makes errors.

## Development plan / experience

Plan/documentation should be intention-first: 

- intentions.md lists the intended functionality of the code base

    - IID-SEMANTIC-TAG (for Intention ID). Use semantic tags (e.g., IID-QNA-CORE)
    - In code scripts, always reference the IID if code snippet connected to fulfilling this intention 
    - SID-SEMANTIC-TAG (standard ID) for standards fixed across the codebase.
    - In code scripts, always reference the SID if code needs to adhere here to this standard
    - intentions.md should only contain intentions and standards, and if they are already implemented or still to do (TODO)
    - Should allow new coding agents to reconstruct functionality
    - Should allow coding agent instances to find code (search IIDs or SIDs) and make sure to adhere to agreed standards


- README.md lists instructions for users of codebase

## Coding instructions

- **Refactoring Rule:** When refactoring or moving code, you must preserve any linked IID or SID comment tags.

- Coding workflow
        - Plan
    - Discuss/ask questions/propose alternatives
    - Focus on all mentioned connected intentions and standards
        - Propose changes to intentions or standards if suitable
        - Write plan, mention IID and SID where appropriate
        - Implement
        - Test
        - Save plan and execution in agent/done/short_plan_name.md
            - should contain: Linked IID/SID, Decisions taken, 
        - Commit
            - should name linked IID/SID and plan_name
    - Track only code and key .md files: intentions.md, CLAUDE.md, README.md, standards.md, but do not track lecture content or done plans, etc.

## Deployment (Railway)

- Project: `victorious-energy` on Railway — **three live services from this one repo** (IID-MULTI-DEPLOY):

| Service | Config (via `TEACHBOT_CONFIG`) | Content | Auth | URL |
|---------|-------------------------------|---------|------|-----|
| `teachbot` (**offline since 2026-10-22**, Predictions lecture finished) | `config.yaml` (default) | `content/` | login required | was https://teachbot-production-2e85.up.railway.app |
| `teachbot-public` | `config_public.yaml` | `content_public/` | none (free public) | https://teachbot-public-production.up.railway.app |
| `teachbot-dcm` | `config_dcm.yaml` | `content_dcm/` | none (free public) | https://teachbot-dcm-production.up.railway.app |
| `teachbot-timeseries` | `config_timeseries.yaml` | `content_timeseries/` | login (`stud.unibas.ch`) | https://teachbot-timeseries-production.up.railway.app |

- `teachbot` (Predictions lecture, Heidelberg) was taken offline 2026-10-22; it is no longer in
  `scripts/deploys.py`, the health matrix or the CI smoke test (which now pings the public instance).
  While it ran, it deployed automatically on every push to `master` via the GitHub connection.
- `teachbot-dcm` is a second free public Q&A instance for an introductory discrete choice modelling
  class (link handed out via QR code). Its content folder currently holds generic introductory
  notes (`content_dcm/dcm_intro.md`); replace/extend with the actual lecture material and
  redeploy manually (same procedure as `teachbot-public`, `--service teachbot-dcm`). Log Sheet:
  "Lectos DCM logs".
- `teachbot-timeseries` is a login-protected Q&A instance for a Basel course "Univariate Time Series
  Analysis" (domain `stud.unibas.ch`, model `openai/gpt-6-luna` since 2026-10-06
  (was `deepseek/deepseek-v4-flash-0731`), own OpenRouter key,
  own `CHAINLIT_AUTH_SECRET`). Content folder `content_timeseries/` has five courses
  (IID-MULTI-COURSE, since 2026-10-11): `utsa01/`, `utsa02/`, `utsa03/` — Q&A per chapter, each
  deck as `.qmd` + `.html` plus the chapter script; ch. 2 and 3 get the earlier scripts via
  `extra_content` — then `cards/` (only the knowledge cards, `content_from_viewer: true`,
  IID-CONTENT-FROM-HTML) and `assignment1/` (Assignment 1 & Exercise 1 helper,
  IID-ASSIGNMENT-HELP). Source files come from
  `junctions/lecture_timeseries/` (gitignored junction to `Dropbox/teaching/lecture_timeseries`)
  and `../graph/site/index.html`; **copy them with `python scripts/sync_timeseries.py`**
  (`--check` only reports), which keeps each deck's `.qmd` and `.html` together. The
  course list is in the script's `COURSES` dict (add a ch. 4 there + a `utsa04/_meta.yaml`). **The repo is public: `*_solution.qmd` is gitignored**, so deploy this
  service with `railway up --service teachbot-timeseries --no-gitignore --detach`, which
  uses `.railwayignore` (= `.gitignore` minus the solution rule; keep both in sync).
  **Thinking is off by default here** (`llm.reasoning: false`, IID-LLM-THINKING) because
  thinking delays the first visible token (deepseek: 10-25s; Luna: ~3s); students can switch to
  "Thorough (thinks first, slower)" in the ⚙ Chat Settings menu. Manual deploys like the
  public instances (`--service teachbot-timeseries`). Log Sheet: "Lectos Timeseries logs".
  The weekly archive script only covers the main Sheet.
- **QR codes** for handing out links: `python scripts/make_qr.py` (needs `pip install "qrcode[pil]"`)
  writes `qr/teachbot_<name>_qr.png/.svg`; URLs are listed in `scripts/deploys.py` (`DEPLOYS`), shared with the health check.
- **Daily health check** (IID-HEALTH-MONITOR): `.github/workflows/health.yml` calls `/health` on
  every instance at 05:17 UTC; a failure = GitHub failure mail to the account that last changed the
  cron line. A new instance → add it to `scripts/deploys.py` **and** the workflow matrix
  (`tests/health.py` checks they match). Manual run: `python scripts/health_check.py`.
- **Start command:** `railway.toml` (nixpacks + `chainlit run ...`) is honoured by the two older
  services, but a service created via `railway add` in 2026-09 (`teachbot-dcm`) builds with
  Railpack and ignored `railway.toml` completely (ran `python app.py` → HTTP 502). `Procfile`
  (`web: chainlit run app.py --host 0.0.0.0 --port $PORT`) is read by both builders and fixes
  this — keep it in sync with `railway.toml`.
- **`teachbot-public`, `teachbot-dcm` and `teachbot-timeseries` do NOT auto-deploy** — Railway refuses to attach the GitHub repo to the
  second service ("Auto deploy unavailable", a Railway↔GitHub App state mismatch, unresolved
  2026-08-28). After pushing changes that should reach the public instance, deploy it manually
  from a clean checkout of `master`:

  ```bash
  railway up --service teachbot-public --detach
  ```

  (Uploads the local working tree — make sure it matches the pushed commit. Alternative if this
  becomes annoying: a GitHub Actions job running `railway up` with a Railway project token.)
- Each service has its **own** `OPENROUTER_API_KEY` (the public one is spend-capped) and its own
  log Sheet ("Lectos public logs" for the public instance).
- **Always pass `--service teachbot` / `--service teachbot-public`** to `railway deployment list`,
  `railway logs`, `railway variables`, `railway redeploy`. The CLI on this machine is linked to
  **`teachbot-public`** by default (`railway status` shows it), so a bare command silently reports
  on the public instance — e.g. polling `railway deployment list` for a push-triggered build will
  never see it (2026-09-03).
- The public instance's lecture material is published as viewable HTML at
  https://schmidtpk.github.io/materials/predictions-part1/ (repo `Schmidtpk/materials`,
  rendered with Quarto from the same `.qmd` sources; linked in `content_public/_welcome.md`).
- **Re-sync public content** after editing the Part I originals:
  `Copy-Item content\_shared\script0.qmd,content\qna_part1\script1.1.qmd,content\qna_part1\script1.2.qmd content_public\`
  then re-render/push the HTML in `Schmidtpk/materials` (needs the `plots/` folder from
  `Dropbox\teaching\Lecture Predictions 2026\Rproj Predictions`).

```bash
# Link project (once per machine, after railway login)
railway link --project victorious-energy

# Which service is the CLI linked to? (currently teachbot-public)
railway status

# Check deployment status of the MAIN instance (omit --service = public instance!)
railway deployment list --service teachbot

# Stream runtime logs
railway logs --service teachbot

# Stream build logs
railway logs --build --service teachbot

# Set/update an environment variable
railway variables set KEY=value --service teachbot

# Trigger a manual redeploy
railway redeploy --yes --service teachbot
```

- Secrets must be set as Railway variables — never committed to git:
  - `OPENROUTER_API_KEY` — LLM access via OpenRouter
  - `GOOGLE_SERVICE_ACCOUNT_JSON` — service account key for Sheets logging (IID-SHEETS-LOG)
  - `CHAINLIT_AUTH_SECRET` — JWT secret for student sessions (IID-AUTH-BASIC)
- Content in `content/` is tracked in git and deployed with the app

## Stack

- Python 3.11+, Chainlit 2.x (SID-STACK)
- LLM via OpenRouter, model `google/gemini-3-flash-preview` (SID-LLM-PROVIDER)
- Config in `config.yaml` + `.env` for secrets (SID-API-CONFIG)
- Run: `.venv\Scripts\python -m chainlit run app.py`

### Choosing a model and its thinking option (IID-LLM-THINKING)

**Whenever you first consider a model together with a thinking/reasoning option — adding it
to `llm:` or to `student_model_choices` — check that the thinking parameter is actually
accepted for that model before configuring it. Never assume it is.**

```bash
python scripts/check_reasoning_support.py <model-id> --live
python scripts/check_reasoning_support.py --config config_timeseries.yaml --live
```

It reports two different things, both of which matter:

1. **How many of the model's OpenRouter providers declare `reasoning`.** OpenRouter picks a
   provider per request, so anything short of *all* of them makes the setting a lottery
   rather than a guarantee.
2. **Whether a live request with `reasoning=false` actually stops the chain-of-thought.**
   Declared support does not imply the model obeys.

Only wire the option into a config once both come back clean. Record the numbers in the
config comment, as `config_timeseries.yaml` does — the next person should not have to re-run
it to know why the value is what it is.

Why this matters: whether a model reasons dominates its time-to-first-token, and that is what
the student experiences as the app hanging. A reasoning model buys little for grounded Q&A
over supplied lecture notes and cost `teachbot-timeseries` a 13.7% failure rate
(IID-STREAM-RESILIENCE). Verified 2026-09-22 for `deepseek/deepseek-v4-flash-0731`: 29/29
providers, honoured, first-content 11.3s -> 1.2s with reasoning off. Verified 2026-10-06 for
`openai/gpt-6-luna`: 7/7 providers, honoured, first-content 3.4s -> 1.0s.

## Multi-course mode (IID-MULTI-COURSE)

Place non-`_`-prefixed subfolders under `content/`. Each needs a `_meta.yaml` with at least `lecture_name`. Optionally add `_system_prompt.md` and `_welcome.md` for per-course overrides; otherwise root `content/` versions are used as fallbacks. When no subfolders exist, the app runs in single-course mode (no profile chooser).

**`_meta.yaml` format:**
```yaml
lecture_name: "Course Name"           # required; shown in profile chooser (full name, not folder name)
order: 1                              # optional; controls sort order in chooser (default 999)
description: "**Markdown** description"  # optional; rendered as markdown in chooser
model: "google/gemini-3-flash-preview"   # optional LLM override
temperature: 0.3                          # optional LLM override
max_tokens: 2048                          # optional LLM override
first_date: 2026-05-01                # optional; inclusive lower bound (server local date)
last_date:  2026-05-15                # optional; inclusive upper bound (server local date)
extra_content:                        # optional; shared files (relative to content/ root)
  - _shared/script0.qmd               #   injected BEFORE the course's own folder content
access:                               # optional; IID-COURSE-ACCESS — who may SEE this course
  allowed_domains:                    #   (omit the whole block = everyone who can log in)
    - stud.uni-heidelberg.de
  allowed_emails:
    - tutor@gmail.com
```

**Per-course access (`access`, IID-COURSE-ACCESS):** restricts which logged-in users see the
course in the profile chooser. Matching uses the same rule as the login allowlist
(IID-AUTH-BASIC): the user's email domain must be in `allowed_domains` or the address in
`allowed_emails` (case-insensitive). A user still has to pass the global login allowlist
first — `access` narrows, it never widens. Omit the block for the previous behaviour
(visible to everyone). A block that admits nobody, a non-mapping value, an unknown key, or a
non-list entry → loud startup failure naming the folder. With auth disabled (public instance)
a restricted course is hidden from everyone and a startup WARNING is printed. `on_chat_start`
re-checks the rule, so a stale tab cannot open a hidden course.

**Shared content (`extra_content`):** files listed here are loaded in addition to the course
folder — used to share one file across courses without duplication (e.g. the intro/syllabus
`content/_shared/script0.qmd` included in all three Q&A parts). Paths are relative to `content/`;
a missing file → loud startup failure naming the folder. The `content/_shared/` folder is
`_`-prefixed, so it is never treated as a course itself.

**Availability window:** `first_date` and `last_date` are both optional and both inclusive — omit either for an open-ended window. Comparison uses the server's local date (Railway = UTC). A course outside its window is hidden from the profile chooser; when at least one bound is set, an "Available …" line is appended to the chooser description. Invalid date or `first_date > last_date` → loud startup failure naming the folder.

**Fallback chain:** `_system_prompt.md` / `_welcome.md`: subfolder → `content/` root. LLM settings: `_meta.yaml` → `config.yaml`. Missing `_meta.yaml` or missing `lecture_name` → startup error.

## Learning-goals practice mode (IID-LEARN-GOALS)

Set `mode: learning_goals` in a course's `_meta.yaml` to turn it into a goal-drill experience instead of
plain Q&A. The course folder then also needs a `_learning_goals.yaml`:

```yaml
goals:
  - id: bayes_rule              # required, unique, stable (it is the per-student progress key)
    title: "Bayes' rule"        # optional short label
    goal: "Student can state Bayes' rule and apply it to a numerical example."
    material: |                 # optional: code/formulas/data the student must literally see
      ```
      P(A|B) = P(B|A) P(A) / P(B)
      ```
  - id: ...
```

**`material`:** anything the student must have in front of them to answer (pseudocode, formulas,
a small dataset). The app appends it **verbatim below the opening question** (and the diagnose
call sees it too), so its display never depends on the LLM copying it out of the goal text —
the LLM is instructed to refer to it, not reproduce it. Must be a string if present (validated
at startup).

Per session the app loads the student's completed goals, **samples one uncompleted goal at random**, and
injects **only that goal** into the system prompt. The bot poses a test question and gives Socratic
feedback; when satisfied it suggests clicking **✅ Mark goal complete**, which records the goal and serves
a new one (the dialogue continues until clicked). When all goals are done, a completion message is shown.
Known limitation: a mid-goal page reload (e.g. iPad Safari evicting a backgrounded tab) starts a fresh
session and may re-sample a different goal than the one in progress — a deterministic per-student seed
was tried to pin the same goal across such reloads, but was reverted 2026-07-20 because under session-churn
conditions it instead relocked students onto one goal, silently regenerating/rewording its opening question
dozens of times while resetting in-session mastery progress on every restart (see `IID-LEARN-GOALS`).

- **Persistence (survives Railway redeploys):** a `progress` worksheet in the Sheet named by
  `sheets_log_id` — columns `timestamp, user_email, course, goal_id` (auto-created). Without Sheets,
  falls back to local `progress/<email>.json` (gitignored). **Requires `IID-AUTH-BASIC`** for a stable
  `user_email`; with auth disabled, progress is in-session only.
- **Validation:** `mode: learning_goals` with a missing/empty `_learning_goals.yaml`, or duplicate/empty
  goal ids → loud startup failure naming the folder.
- Example course: `content/learn_part1/`.

### Diagnostic two-step turns (IID-LEARN-DIAGNOSE)

In learning-goals mode, each student answer is handled by **two LLM calls** instead of one:

1. **Diagnose** — a non-streamed structured-JSON call (`src/tutor_loop.py` → `llm_client.complete_json`)
   judges the answer against the goal + lecture content + the **full student↔tutor dialogue for this
   goal** (points made in earlier turns are credited, not flagged as omissions; mastery is cumulative),
   ranks the misunderstandings, and picks the single most important one plus a `tactic`
   (`explain`/`probe`). Shown as an "Analysing your answer…" step; the JSON is logged internally as
   role `diagnosis` (never shown to the student).
2. **Act** — the streamed reply, seeded to address **only that one point** and re-ask the fixed
   **"big question"** (the question first posed for the goal, held constant for the whole goal).

`mastered` → affirm + suggest ✅. `requested_solution` (student explicitly asks for help, a summary,
or the solution) → the tutor provides the full answer to the big question, then invites the student
to restate it in their own words — explicit requests are honoured, never met with another probe.
A failed/empty diagnose call degrades to generic Socratic feedback, so a flaky model never breaks
the turn. Both calls use the course model.

- **Editable prompt:** `content/_diagnose_prompt.md` (root default), overridable per course via
  `content/<course>/_diagnose_prompt.md` (same subfolder→root fallback as `_system_prompt.md`).
- The plain Q&A path (IID-QNA-CORE) is untouched — only `mode: learning_goals` courses use this loop.

## Viewer panel: HTML next to the chat (IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK, IID-CONTENT-FROM-HTML)

`*.html` files in a course folder (Quarto reveal.js decks, the `../graph` card viewer as
`cards.html`, any page) are shown in a panel next to the chat: Chainlit's side view on
desktop (opens by itself), a full-screen sheet on phones (header button "📖 Slides" /
"💬 Chat"). Optional `viewer:` in `_meta.yaml` (`false` or a list of `{file, label}`).
No HTML → nothing changes (tested in `tests/content_view.py`).

- **Before each Q&A answer** the open slide/card goes into the request (not the history):
  the page in full first, then previous/next slide, card neighbours and related cards
  (slides ↔ cards via the cards' `sources`). The history keeps a one-line marker.
- **Links:** the system prompt lists every slide/card id; the bot writes
  `[text](view:DOC/LOC)`, rewritten after streaming to `/viewer/<course>/<file>#…`.
- **Logs:** `viewer` field / last Sheet column = page open when the student asked.
- **Files are gitignored** (`content_timeseries/**/*.html`, a deck is ~7 MB): copy them with
  `python scripts/sync_timeseries.py`, then deploy with
  `railway up --service teachbot-timeseries --no-gitignore --detach` (`.railwayignore` does not
  exclude them). Re-sync + redeploy after re-rendering slides or rebuilding the graph. Without
  the copied HTML, `config_timeseries.yaml` does not start (the `cards` course has nothing to load).
- **HTML-only courses** (IID-CONTENT-FROM-HTML): `content_from_viewer: true` in `_meta.yaml` makes
  the HTML text the lecture content (`ViewerSet.as_content`); otherwise HTML never enters it and
  a deck needs its same-stem `.qmd` next to it (startup WARNING if missing, SID-CONTENT-RENDER).
- **Header button word** follows the documents (Slides / Cards / Pages). `public/viewer.js` is
  cached by browsers: bump `?v=` in `.chainlit/config.toml` (`custom_js`) whenever it changes.
- **Relies on Chainlit 2.11 internals** (canvas side view, `set_sidebar_elements`, window-message
  forwarding) — `tests/content_view.py` fails loudly if a Chainlit upgrade changes them.
- **Local testing:** run only ONE local instance — a second one that fails to bind the port
  deletes the shared `.files/` folder on exit and breaks the first.

## Key files

| File | IID/SID | Description |
|------|---------|-------------|
| `app.py` | IID-CHAT-SHELL1, IID-QNA-CORE, IID-AUTH-BASIC, IID-MULTI-COURSE, IID-STREAM-RESILIENCE, IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK | Chainlit entry point. `/viewer/<course>/<file>` route, `on_window_message` (viewer panel), page context per request, `view:` link rewriting. `_stream_assistant` retries a stalled turn, rewinds history on total failure, and shows a "Thinking…" step while a reasoning model works |
| `config.yaml` | IID-EDUCATOR-CONFIG, SID-API-CONFIG | Course + LLM config |
| `requirements.txt` | SID-STACK | Pinned dependencies |
| `.env` | SID-API-CONFIG | API secrets — gitignored, never commit |
| `.env.example` | SID-API-CONFIG | Template for .env |
| `content/_system_prompt.md` | IID-EDUCATOR-CONFIG, IID-QNA-CORE | Editable LLM behaviour instructions; `{{course_name}}` substituted per session. Default fallback for course subfolders that omit their own copy. |
| `content/_welcome.md` | IID-EDUCATOR-CONFIG, IID-CHAT-SHELL1 | Editable first chat message shown to students; `{{course_name}}` substituted per session. Default fallback for course subfolders that omit their own copy. |
| `content/_readme.md` | IID-EDUCATOR-CONFIG, IID-MULTI-DEPLOY | Editable sidebar/welcome panel template; `{{course_name}}` substituted. Per-deploy override: `<content_dir>/_readme.md`. Written to `chainlit.md` (generated, gitignored) at startup because Chainlit only reads that fixed root path |
| `src/course_loader.py` | IID-MULTI-COURSE, IID-COURSE-ACCESS, IID-LEARN-GOALS, IID-UI-CONTENT-VIEW | Discovers course subfolders, loads `_meta.yaml` (incl. `mode`, `access`, `viewer` + `_learning_goals.yaml`), merges LLM config, resolves fallback paths for system prompt and welcome text |
| `src/goals.py` | IID-LEARN-GOALS | Samples one uncompleted learning goal; builds the per-goal system prompt (only one goal in context) |
| `src/tutor_loop.py` | IID-LEARN-DIAGNOSE | Two-step turn: structured `diagnose_answer` (ranks misconceptions, picks top-1 + tactic) + `build_act_instruction` seeding the streamed reply |
| `content/_diagnose_prompt.md` | IID-LEARN-DIAGNOSE | Editable diagnostic instructions (JSON output); default fallback for goals courses that omit their own copy |
| `src/progress_store.py` | IID-LEARN-GOALS | Per-student record of completed goals — Google Sheet `progress` tab (durable) or `progress/<email>.json` fallback |
| `src/content_loader.py` | IID-CONTENT-INJECT | Loads + cleans a content folder; skips `_`-prefixed files (app-config convention) |
| `src/math_delimiters.py` | IID-UI-RENDER | Converts `\(…\)` / `\[…\]` in streamed answers to `$…$` / `$$…$$` (the only forms the chat renders); used in `app._stream_once` |
| `src/llm_client.py` | SID-LLM-PROVIDER, IID-STREAM-RESILIENCE, IID-LLM-THINKING | OpenRouter async client. `stream_events` yields `(reasoning\|content, text)`; `stream_response` is its content-only view. `_reasoning_kwargs` turns `llm.reasoning` into OpenRouter's `extra_body` |
| `scripts/check_reasoning_support.py` | IID-LLM-THINKING | Checks whether a model's providers declare `reasoning` **and** whether a live request honours it. Run before configuring any model with a thinking option |
| `src/viewer_docs.py` | IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK, IID-CONTENT-FROM-HTML | Indexes course HTML (reveal decks, card graph, any page) into slides/cards/pages; builds the per-turn page context, the link catalogue, the HTML-as-lecture-content text; rewrites `view:` links |
| `src/viewer_files.py` | IID-UI-CONTENT-VIEW | Viewer files gzipped once (in memory, warmed at startup) + `If-None-Match` → 304 for `/viewer/...`; Starlette's FileResponse never sends 304 itself |
| `scripts/sync_timeseries.py` | IID-MULTI-COURSE, IID-CONTENT-FROM-HTML, SID-CONTENT-RENDER | Copies the time series decks (`.qmd` + `.html` together), chapter scripts and `cards.html` into `content_timeseries/<course>/`; `--check` reports only |
| `public/elements/HtmlViewer.jsx` | IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT | Viewer panel (Chainlit custom element): document picker + iframe; reports the open slide/card |
| `public/viewer.js` | IID-UI-CONTENT-VIEW, IID-UI-CONTENT-MARK | Chainlit `custom_js`: header button, auto-open on desktop, answer links open in the panel |
| `src/health.py` | IID-HEALTH-MONITOR | `/health` self-check: OpenRouter key + balance, 16-token ping per model in use, log Sheet; cached 10 min (60 s when failed); no amounts/secrets in the JSON |
| `scripts/health_check.py` | IID-HEALTH-MONITOR | Calls `/health` on each instance, explains failures (down / old code / failed check), GitHub annotations + summary. Stdlib only |
| `scripts/deploys.py` | IID-MULTI-DEPLOY, IID-HEALTH-MONITOR | The deployed instances (`DEPLOYS`), used by `make_qr.py` and `health_check.py`; keep in sync with the service table and `health.yml` matrix |
| `.github/workflows/health.yml` | IID-HEALTH-MONITOR | Daily 05:17 UTC, one job per instance; GitHub's failure mail is the alert |
| `src/chat_logger.py` | IID-CHAT-LOG, IID-SHEETS-LOG | Writes `logs/<uuid>.jsonl` per session; appends rows to Google Sheet if `sheets_log_id` set |
| `src/auth.py` | IID-AUTH-BASIC | Allowlist check, user load/save, bcrypt hash/verify |
| `users.yaml` | IID-AUTH-BASIC | Runtime user registry (gitignored, auto-created on first registration) |
| `credentials/` | IID-SHEETS-LOG | Gitignored folder for Google service account JSON key |
| `scripts/make_qr.py` | IID-MULTI-DEPLOY | Generates QR codes for every deployed instance into `qr/` (PNG + SVG). QR codes live **only** in `qr/`, never in `public/` (Chainlit static assets, deployed) |
| `scripts/archive_sheet.py` | IID-SHEETS-LOG | Downloads Sheet → `exports/sheets_backup_<date>.csv`, then clears it |
| `scripts/archive_sheet.bat` | IID-SHEETS-LOG | Windows Task Scheduler wrapper for the archive script |
| `scripts/render_chats.py` | IID-CHAT-VIEW | Reads all `exports/*.csv` backups → `exports/chats.html` self-contained viewer (`--input`/`--output` for a subset) |
| `scripts/weekly_report.py` | IID-WEEKLY-REPORT | Wednesday Timeseries report: archive Sheet → chats.html + agent inputs → headless Claude agent → Gmail |
| `scripts/weekly_report.bat` | IID-WEEKLY-REPORT | Task Scheduler wrapper, logs to `exports/timeseries/weekly_log.txt` |
| `.claude/skills/weekly-report/SKILL.md` | IID-WEEKLY-REPORT | The agent's instructions: report sections, what counts as a bad answer. Edit this to change the report |
| `exports/` | IID-SHEETS-LOG | Gitignored folder for weekly CSV backups of Google Sheet |
| `intentions.md` | — | All IIDs and their lifecycle status |
| `standards.md` | — | All SIDs (cross-cutting standards) |

## Data Management (IID-SHEETS-LOG)

The Google Sheet (`sheets_log_id` in `config.yaml`) accumulates one row per chat turn. To keep it lean, a weekly archive script downloads the data and clears the sheet.

- **Script:** `scripts/archive_sheet.py` — downloads all rows to `exports/sheets_backup_<date>.csv`, then clears the sheet. The `SheetsLogger` auto-recreates the header on the next student interaction.
- **Credentials:** `credentials/service_account.json` (gitignored). Extract from Railway if needed: `railway variables --json`.
- **Backups:** `exports/` folder (gitignored — contains student data, never commit).

```bash
# Run manually
python scripts/archive_sheet.py
```

**Automated weekly run (Windows Task Scheduler):**
Register once in a terminal (run as Administrator or normal user):
```bat
schtasks /create /tn "teachbot-archive" /tr "\"C:\Users\Schmidt\Dropbox\R packages\teachbot\scripts\archive_sheet.bat\"" /sc weekly /d SUN /st 08:00
```
Output is appended to `exports/archive_log.txt`. To check or remove the task:
```bat
schtasks /query /tn "teachbot-archive"
schtasks /delete /tn "teachbot-archive" /f
```
`archive_sheet.py --config config_<x>.yaml --out-dir <dir>` archives another instance's Sheet;
`--keep` downloads without clearing. Rows are only removed after the CSV is verified, and if
students wrote during the download only the archived rows are deleted.

## Weekly Timeseries report (IID-WEEKLY-REPORT)

Every Wednesday (or at the next PC start, if missed) a mail to `REPORT_TO` reports on the
week's `teachbot-timeseries` chats: stats, tool problems, worst AI answers (checked against
`content_timeseries/`), a verdict on every student flag, what students focused on and
struggled with, suggestions — plus all flags verbatim and `chats.html` attached.

- **Pipeline** (`scripts/weekly_report.py`): archive + clear the "Lectos Timeseries logs" Sheet →
  `exports/timeseries/week_<date>/` with `chats.html`, `transcripts.md`, `flags.md`, `stats.json` →
  `claude -p` (Opus) follows `.claude/skills/weekly-report/SKILL.md` and writes `report_body.html`
  (read-only on the repo, may write only into the week folder, no shell, `.env`/`credentials/` denied)
  → Gmail SMTP. If the agent fails, the mail still goes out with stats + flags, subject "[analysis failed]".
- Each session in `transcripts.md`/`stats.json` names its **course** (chapter, cards, helper), and a
  student turn shows the slide/card that was open (`viewer` column). SKILL.md maps course names to
  `content_timeseries/` folders — update it when courses are added or renamed.
- **Once per ISO week**, resumable: `exports/timeseries/state.json` records the stage
  (archived/prepared/analysed/sent); a crashed run continues without downloading again.
- **Secrets** in `.env`: `GMAIL_USER` (sending account, a separate Gmail), `GMAIL_APP_PASSWORD`
  (its app password; spaces are fine), `REPORT_TO` (recipient; default `GMAIL_USER`). The agent uses the Claude Code login of the Windows user, so the task must
  run as that user.
- **Who counts as student:** e-mails in `auth.allowed_domains` of `config_timeseries.yaml`, minus
  `weekly_report.non_student_emails` (the lecturer's test account `me@stud.unibas.ch`); others are
  marked NON-STUDENT and excluded from student counts and the focus/struggle analysis.

```bash
python scripts/weekly_report.py                    # normal run (skips if this week is done)
python scripts/weekly_report.py --force            # run again this week (downloads what is new)
python scripts/weekly_report.py --keep --skip-agent --no-send   # dry run: no clearing, no agent, no mail
python scripts/weekly_report.py --week-dir exports/timeseries/week_2026-09-26 --no-send   # redo the analysis
```

**Task Scheduler** (Wednesdays 07:00; if missed, starts as soon as the PC is on):
```powershell
$a = New-ScheduledTaskAction -Execute "C:\Users\Schmidt\Dropbox\R packages\teachbot\scripts\weekly_report.bat"
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At 7am
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "lectos-timeseries-weekly" -Action $a -Trigger $t -Settings $s
# check / remove
Get-ScheduledTask lectos-timeseries-weekly | Get-ScheduledTaskInfo
Unregister-ScheduledTask lectos-timeseries-weekly -Confirm:$false
```

## Authentication (IID-AUTH-BASIC)

- Students log in at the Chainlit login screen using their **institutional email as username** and a password of their choice.
- **First login = automatic registration** — no separate sign-up flow. The student's account is created on first successful login.
- Auth is controlled by `config.yaml` under the `auth:` key:

```yaml
auth:
  allowed_domains:
    - stud.uni-heidelberg.de   # all addresses at this domain are admitted
  allowed_emails:
    - guest@gmail.com          # individual addresses regardless of domain
```

- **Disable auth** (make app fully public): set both lists to `[]` — the login screen disappears.
- **Add a new domain or individual email**: edit `config.yaml`, redeploy.
- Registered users are stored in `users.yaml` (gitignored, created at runtime). Each entry holds the email and a bcrypt-hashed password — no plaintext passwords.
- **Password reset**: remove the student's entry from `users.yaml`; they re-register on next visit.
- **Railway caveat**: `users.yaml` lives on the dyno filesystem and is lost on redeploy. Export it before redeploying if accounts must be preserved.

```bash
# Regenerate the JWT secret (logs out ALL active sessions)
chainlit create-secret
railway variables set CHAINLIT_AUTH_SECRET="<new-secret>"
# Also update .env locally
```

## Testing

| File | IID | Description |
|------|-----|-------------|
| `tests/runner.py` | IID-TEST-LLM-EVAL | Runs test cases through the LLM pipeline (no Chainlit) |
| `tests/judge.py` | IID-TEST-LLM-EVAL | LLM-as-judge: grades a response PASS/FAIL against a rubric |
| `tests/compare.py` | IID-TEST-MODEL-COMPARE | Runs all cases × all variants, writes `reports/compare_*.md` |
| `tests/learn_goals.py` | IID-TEST-LLM-EVAL, IID-LEARN-GOALS | Multi-turn harness for learning-goals mode: judges the opening question + the tutor's feedback to simulated students |
| `tests/cases/learn_part1_goals.yaml` | IID-TEST-LLM-EVAL, IID-LEARN-GOALS | Goal cases for "Practice: Part I": per-goal `question_rubric` + student personas with `feedback_rubric` |
| `tests/stream_resilience.py` | IID-STREAM-RESILIENCE | Offline: retry, history rewind, stream cleanup, reasoning-as-liveness, Thinking step |
| `tests/math_delimiters.py` | IID-UI-RENDER | Offline: LaTeX delimiter conversion, at every possible chunk split; code untouched |
| `tests/model_choices.py` | IID-LLM-THINKING, IID-STUDENT-MODEL-CHOICE | Offline: `reasoning` translation, choice validation, chooser behaviour, all configs import |
| `tests/content_view.py` | IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK, IID-CONTENT-FROM-HTML | Offline: HTML indexing, page context, links, window messages, route order, Chainlit internals, `content_from_viewer`, the time series course layout, no-HTML courses unchanged (needs the synced HTML) |
| `tests/health.py` | IID-HEALTH-MONITOR | Offline: key/balance/Sheets/model checks, cache, `/health` route, monitor's failure texts, workflow matrix = `DEPLOYS` |
| `tests/smoke.py` | IID-TEST-SMOKE | HTTP ping + optional Playwright chat simulation of live app |
| `tests/cases/qna.yaml` | IID-TEST-LLM-EVAL | Q&A test cases — edit to match lecture content |
| `tests/cases/behavior.yaml` | IID-TEST-LLM-EVAL | Behavior/hallucination guard test cases |
| `tests/configs/variants.yaml` | IID-TEST-MODEL-COMPARE | Model/prompt variants for comparison runs |
| `.github/workflows/ci.yml` | IID-TEST-SMOKE | GitHub Actions: HTTP ping on every push to master |

```bash
# Run a single case with LLM-as-judge verdict
python tests/runner.py --case deterministic_vs_probabilistic --judge

# Run all Q&A cases
python tests/runner.py --cases tests/cases/qna.yaml --judge

# Validate config + content without any LLM calls (safe for CI dry-run)
python tests/runner.py --dry-run

# Full model comparison → reports/compare_<timestamp>.md
python tests/compare.py

# Deployment smoke test (HTTP ping only — what CI does)
python tests/smoke.py

# Deployment smoke test with Playwright chat simulation (on-demand)
# Requires: pip install playwright && playwright install chromium
python tests/smoke.py --full

# Use a stronger judge model for evaluation
JUDGE_MODEL=anthropic/claude-opus-4-6 python tests/compare.py

# Learning-goals mode (IID-LEARN-GOALS): check opening questions + feedback quality
python tests/learn_goals.py                          # all goals in Practice: Part I
python tests/learn_goals.py --goal why_probabilistic # one goal
python tests/learn_goals.py --no-judge               # transcripts only, no grading
# The default judge (config model) can be flaky (empty output → ERROR verdicts);
# use a steadier grader for reliable verdicts:
JUDGE_MODEL=anthropic/claude-opus-4-6 python tests/learn_goals.py
```

**Test case authoring:** Add/edit cases in `tests/cases/*.yaml` — no Python required.
Each case needs an `id`, `question`, `rubric`, and optional `tags`.
`reports/` is gitignored; comparison reports are local only.
