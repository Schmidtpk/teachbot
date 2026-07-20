# intentions.md — Lectos

Intended functionality of the Lectos codebase. Each intention has a unique IID tag and a lifecycle status.
Reference IIDs in code comments wherever a snippet implements an intention. See also: standards.md.

## Roles

- admin:
    - lecturer 
    - shares content
    - access to chats
    - access to feedback
- student
    - uses UI
    - provides feedback

## Lifecycle Legend

| Tag | Meaning |
|-----|---------|
| `CANDO` | Potentially useful, not yet planned |
| `TODO` | Planned, not yet started |
| `v1` | Required for next release |
| `v2` | Required for next release |
| `IN_PROGRESS` | Currently being implemented |
| `EXPERIMENTAL` | Prototype / proof-of-concept |
| `DONE` | Implemented and tested |
| `DEPRECATED` | Removed or superseded |

## UI

### IID-UI-RENDER
**Lifecycle:** v1
**Description:** LLM responses are rendered as Markdown in the chat UI. LaTeX math (inline `$...$` and block `$$...$$`) must be rendered correctly. Implemented via Chainlit's built-in renderer (see SID-STACK).

### IID-UI-CONTENT-VIEW
**Lifecycle:** CANDO
**Description:** The UI can display course material alongside the chat. Students can open/view the material.
**Inputs:** `content/` folder (`.qmd` + `.md` files) or AI generated content.
**Outputs:** Rendered HTML pages accessible within or adjacent to the chat UI.
**Success criteria:**
- Rendered output preserves math, code blocks, and slide structure.
- A student can navigate to a specific lecture/section from within the chat (e.g. via a link or button).
**No-Goals:** In-browser editing of content.
**v1 implementation note:** Pre-render files to scrollable HTML. Mount the output directory as static files on Chainlit's FastAPI server. Bot responses include Markdown links to `#section-id` anchors (Quarto auto-generates these). Renders in a new browser tab — no custom UI component needed. See SID-CONTENT-RENDER.

### IID-UI-CONTENT-MARK
**Lifecycle:** CANDO
**Description:** The agent (or student) can highlight or annotate specific passages in the displayed course material — e.g. the bot response links to a section anchor in the rendered HTML, scrolling the content panel to the relevant passage or visually marking it.
**Inputs:** Section/anchor identifier produced by the LLM response (e.g. a fragment URL `#section-id`).
**Outputs:** Visual highlight or scroll-to in the content viewer panel.
**Success criteria:**
- Bot can reference a specific slide or section and the UI reflects that reference visually.
**No-Goals:** Persistent student-side annotations, shared annotations across students.


## Content

### IID-LECTURE-CONTENT
**Lifecycle:** v1
**Description:** Lecture content lives in a `content/` folder: Quarto `.qmd` slide files plus a `syllabus.md` (or `.qmd`). This folder is the single source of truth for all content-related IIDs.

### IID-CONTENT-INJECT
**Lifecycle:** v1
**Description:** At app startup, read all files in the active course folder, strip YAML frontmatter and Quarto-specific syntax, concatenate into a single plain-text string, and inject into the LLM system prompt (see SID-LLM-PROVIDER). No vector store or embedding; relies on the model's large context window. In multi-course mode (IID-MULTI-COURSE), `load_content` is called with the selected course subfolder path, not the root `content/` dir.
**Inputs:** Course content folder (`.qmd` files + syllabus) — root `content/` in single-course mode, or specific subfolder in multi-course mode.
**Outputs:** System prompt string passed to the LLM at session start.
**Success criteria:**
- All content files are loaded and visible in the system prompt.
- App fails loudly if `content/` folder is missing or empty.
**No-Goals:** Chunking, embedding, retrieval — those are IID-LECTURE-INGEST (v2).

### IID-LECTURE-INGEST
**Lifecycle:** v2
**Description:** Ingest lecture content into a vector store for RAG retrieval. Replaces IID-CONTENT-INJECT for larger corpora.
**Inputs:** Raw lecture files in `content/`.
**Outputs:** Chunked, embedded documents in a local or hosted vector store.
**Success criteria:**
- Educator can point to a folder and trigger ingestion.
- Retrieval returns relevant chunks for a sample query.


## UI 

### IID-CHAT-SHELL1
**Lifecycle:** v1
**Description:** Core chat UI shell built with Chainlit (see SID-STACK): message thread display, user input field, streaming send/receive flow, Markdown + LaTeX rendering. No feedback widgets in v1 — those are IID-CHAT-SHELL (v2).


### IID-CHAT-SHELL
**Lifecycle:** v2
**Description:** as v1, but add feedback with widgets (e.g. thumbs up/down, free-text comment) on each bot message, and persist feedback events to a database for later analysis.
**Partial (DONE via IID-STUDENT-FEEDBACK-STORE):** 🚩 flag button + free-text comment on each AI message, stored in JSONL + Sheets.
**Remaining:** thumbs up/down widget, database-backed storage.
**No-Goals:** Native mobile app.

## Core Mode: QA

### IID-QNA-CORE
**Lifecycle:** v1
**Description:** Single QA mode (no auth, public URL) — any visitor can ask questions and the bot answers using full lecture content injected into context (IID-CONTENT-INJECT). v1 uses full-context stuffing; v2 will use RAG (IID-RAG-RETRIEVAL). Covers both prospective and enrolled students.
**Inputs:**
- `question` (string, required): free-text student question.
**Outputs:**
- `answer` (Markdown string): grounded in lecture content, with source references where possible.
**Success criteria:**
- Answer is factually correct relative to lecture material.
- Answer is relevant to the question.
- Answer cites or paraphrases lecture content, not generic web knowledge.
- Bot stays on topic; politely declines off-topic requests.
- No login required; app is stateless per session from the student's perspective.
**No-Goals:** Personalized recommendations, enrollment actions, external data sources.

### IID-PRECOURSE-QA
**Lifecycle:** DEPRECATED
**Description:** Merged into IID-QNA-CORE for v1 (single mode, no auth distinction).

## Core Mode: Learn

### IID-LEARN-SOCRATIC
**Lifecycle:** TODO
**Description:** Learn mode — Socratic dialogue to guide a student through a topic. Bot asks probing questions, gives hints, and confirms understanding before moving on.
**Inputs:**
- `topic` (string, required): topic or concept to learn.
- Optional: difficulty level, prior knowledge flag.
**Outputs:**
- Multi-turn dialogue: questions, hints, confirmations, and brief explanations.
**Success criteria:**
- Bot does not reveal the answer immediately; leads student through reasoning steps.
- Bot detects correct vs. incorrect student responses and adapts next prompt.
- Session ends with a summary of what was learned.

### IID-LEARN-GOALS
**Lifecycle:** IN_PROGRESS
**Description:** Learning-goals practice mode — a course behavioral mode (`mode: learning_goals` in
`_meta.yaml`) that drills a student through a list of learning goals one at a time. At session start
the app loads the student's already-completed goals, **samples one uncompleted goal at random**, and
injects **only that goal** into the system prompt (on top of the normal lecture content,
IID-CONTENT-INJECT).
**Known limitation:** a mid-goal page reload (e.g. iPad Safari evicting a backgrounded tab) starts a
fresh Chainlit session and may re-sample a different goal than the one in progress. A deterministic
per-student seed (`(student, course, completed-set)` → same goal across such reloads) was added
2026-07-08 (plan `goal_sticky_on_reload`) and reverted 2026-07-20 (plan `goal_seed_rewind`): under a
session-churn condition (frequent reconnects, root cause undiagnosed — see agent/done for the
investigation) it instead relocked students onto one goal, silently regenerating/rewording its opening
question dozens of times per hour while resetting in-session mastery progress (`goal_dialogue`,
`current_big_question`) on every restart — a worse and more confusing failure than the occasional
reload it fixed. Revisit only alongside a fix for the underlying reconnect churn, or via durable
per-goal session state instead of hidden RNG determinism.
The bot poses a test question on the goal, gives Socratic feedback, and — when it judges the goal
demonstrated — *suggests* the student click the **"✅ Mark goal complete"** button. The button is the
authoritative completion trigger (no LLM "done"-token parsing): clicking it records the goal to the
per-student store and advances to a freshly sampled goal, resetting the context so only one goal is
ever present. When all goals are completed, the student sees a completion message and no goal is served.
Builds on IID-MULTI-COURSE (course folders), IID-CONTENT-INJECT, IID-LEARN-SOCRATIC (dialogue style),
IID-AUTH-BASIC (the per-student key), and IID-SHEETS-LOG (durable store).
**Inputs:**
- `_meta.yaml`: `mode: learning_goals`.
- `_learning_goals.yaml`: `goals:` list of `{id, title?, goal, material?}` — `id` unique + stable (the
  progress key). `material` (string) is anything the student must literally see (pseudocode, formulas,
  data): the app appends it verbatim below the posed opening question and the diagnose call
  (IID-LEARN-DIAGNOSE) sees it, so display never depends on the LLM copying it from the goal text.
- Authenticated `user_email` (required for cross-session persistence).
**Outputs:**
- Per-turn chat (question → answer → feedback), logged as usual (IID-CHAT-LOG, IID-SHEETS-LOG).
- Progress rows `(timestamp, user_email, course, goal_id)` in a `progress` worksheet of the Sheet
  (`sheets_log_id`), or `progress/<email>.json` locally when Sheets is disabled.
**Persistence (per student, survives Railway redeploys):**
- Backend 1: `progress` tab in the configured Google Sheet (reuses `GOOGLE_SERVICE_ACCOUNT_JSON`).
- Backend 2: local `progress/<email>.json` (dev fallback when `sheets_log_id` is blank).
- Backend 3: in-session only when no `user_email` (auth disabled) — nothing persists; logs a warning.
**Success criteria:**
- Only the sampled goal appears in the LLM context; completed goals are not re-sampled until all done.
- Completion is recorded only on button click; the dialogue continues if the student keeps answering.
- Re-login as the same student does not re-serve completed goals; all-done shows a completion message.
- `mode: learning_goals` without a valid non-empty `_learning_goals.yaml` (unique ids) → loud SystemExit;
  a non-string `material` also fails loudly at startup.
- A goal with `material` always displays it verbatim with the opening question (LLM-independent).
**Key files:** `src/goals.py` (sampling + per-goal prompt), `src/progress_store.py` (per-student store),
`src/course_loader.py` (`mode` + `learning_goals` parsing/validation), `src/chat_logger.py`
(`gspread_client` shared helper), `app.py` (`on_chat_start` branch, `complete_goal` action,
`_pose_goal_question`/`_send_actions`/`_stream_assistant` helpers),
`content/learn_part1/` (example course).
**No-Goals:** Mastery scoring / spaced repetition, multiple questions tracked per goal, automatic
(LLM-signalled) completion, ordering/prerequisites between goals.

### IID-LEARN-DIAGNOSE
**Lifecycle:** IN_PROGRESS
**Description:** Agentic two-step turn layered on IID-LEARN-GOALS. Instead of answering each student
reply with a single LLM call, a learning-goals turn runs **(1) diagnose** then **(2) act**:
1. **Diagnose** — a non-streamed, structured-JSON call (`response_format=json_object`) that judges the
   student's latest answer against the current goal + injected lecture content **plus the full
   student↔tutor dialogue for this goal** (so a point the student made in an earlier turn is credited,
   not flagged as an omission; mastery is judged cumulatively over the dialogue). Lists every
   misunderstanding ranked most→least important and selects the **single most important** one, plus a
   `tactic` (`explain` | `probe`). Shown to the student as a subtle "Analysing your answer…" step.
2. **Act** — the existing streamed reply, seeded with an internal instruction so it addresses **only**
   that one point (explains it briefly or asks one probing question) and then re-asks the fixed
   **"big question"** — the question first posed for this goal, held constant for the whole goal so the
   student iterates on the same target until it is clean.
When diagnosis reports `mastered` the bot affirms and suggests the ✅ button. When it reports
`requested_solution` (the student explicitly asked for help, a summary, or the solution — e.g.
"help me", "please tell me") the bot provides the full answer to the big question grounded in the
lecture, then invites the student to restate it in their own words; explicit requests are honoured
rather than met with another probe. When the diagnose call fails/returns nothing it degrades to
generic Socratic feedback (prior single-call behaviour). The diagnosis JSON is logged internally
(role `diagnosis`) for auditing, never shown as an assistant turn.
Builds on IID-LEARN-GOALS, IID-LEARN-SOCRATIC, IID-CONTENT-INJECT; uses SID-LLM-PROVIDER.
**Inputs:**
- `_diagnose_prompt.md` (subfolder → root `content/` fallback) — the diagnostic instructions.
- Cached per session: diagnose prompt text, lecture content, current goal, current big question,
  per-goal dialogue transcript (`goal_dialogue`, reset when a new goal is posed).
**Outputs:**
- One internal `diagnosis` log row (JSON) + the normal streamed assistant reply per student turn.
**Success criteria:**
- Exactly two LLM calls per learning-goals answer; the Q&A path (IID-QNA-CORE) is unchanged.
- The reply targets one misconception and re-asks the same big question until mastery.
- Diagnose failure never crashes the turn — it falls back to generic Socratic feedback.
**Key files:** `src/tutor_loop.py` (Diagnosis, message + act-instruction builders, `diagnose_answer`),
`src/llm_client.py` (`complete_json`), `content/_diagnose_prompt.md` (default prompt),
`src/course_loader.py` (`diagnose_prompt_path`), `app.py` (`_diagnostic_turn`, `on_message` branch,
big-question capture in `_pose_goal_question`).
The diagnose call runs on `llm.diagnose_model` when set (`config.yaml` → per-course `_meta.yaml`
override; see IID-COST-CACHE) — a cheap model for this internal, never-shown JSON call — and falls
back to the course model otherwise. The student's model choice (IID-STUDENT-MODEL-CHOICE) does not
affect the diagnose model.
**Mastery calibration** (student feedback 2026-07-15): the diagnose prompt accepts ANY valid route
to the result (counterexamples, alternative derivations, informal-but-correct wording), treats
mostly-correct answers as mastery (withholding only for gaps central to the goal), and counts a
faithful restatement after a `requested_solution` hand-over as mastery instead of probing further.
Vague/hand-wavy answers and restating the question still never count.
**Session-churn hardening** (student feedback 2026-07-20, plan `session_churn_timeouts`): a
Chainlit-session-restart storm was traced to learning-goals mode being the only mode that makes an
LLM call automatically at session start (posing the opening question) plus two calls per student
turn thereafter, versus Q&A's zero-at-start/one-per-turn — any call left to hang risks exceeding
Chainlit's Socket.IO ping_timeout (engine.io default 20s), causing a silent transport drop and
reconnect that re-runs `on_chat_start` (see `agent/session_churn_fix_handoff.md` for the full
evidence trail). Mitigations: (1) every learning-goals LLM call (`complete_json` in
`src/llm_client.py`, and the shared `_stream_assistant` in `app.py` used for both the opening
question and the act reply) now has an explicit timeout — `DIAGNOSE_TIMEOUT_S` /
`FIRST_TOKEN_TIMEOUT_S`, both 15s — with a graceful fallback (existing empty-`Diagnosis` path for
diagnose; a short "please retry" message for the streamed calls) instead of hanging past the ping
window; (2) `complete_json`'s previously-silent `except Exception: return {}` now logs the
exception type/message/elapsed time to stderr, and all three calls log their duration — prior
investigations found zero error traces specifically because failures were swallowed silently;
(3) the learning-goals branch of `on_chat_start` used to call `load_content`/`build_system_prompt`
up to 3x per session start (once for the base prompt, again inside `build_goal_system_blocks`,
again for the cached `lecture_content`) — now loaded once via `load_course_content` and reused
(`build_system_prompt`/`build_goal_system_blocks` both accept an optional pre-loaded value).
Verified byte-identical output between the reused and freshly-computed paths. Root cause of the
underlying latency/disconnect is not fully confirmed — these are defensive + diagnostic changes;
if churn persists, the new duration/error logs should show what's actually slow.
**No-Goals:** Addressing several misconceptions per turn (top-1 only), an evolving/sharpening big
question (kept fixed per goal).

### IID-COST-CACHE
**Lifecycle:** IMPLEMENTED
**Description:** Keep per-turn LLM cost low despite full-context stuffing (IID-CONTENT-INJECT).
Two levers:
1. **Prompt caching** — every request marks the stable prefix with Anthropic `cache_control`
   breakpoints (`src/llm_client.py::_with_cache_control`): the system message (instructions +
   injected lecture content, the dominant share of every request) and the latest message (so the
   growing history is cached incrementally turn-over-turn). OpenRouter forwards `cache_control` to
   providers with explicit caching (Anthropic bills cache reads at ~0.1x input price, 5-min TTL) and
   ignores it for providers that cache implicitly (OpenAI, DeepSeek, Gemini) — safe for every model
   in the student chooser. In learning-goals mode the system prompt is **split into two blocks**
   (`src/goals.py::build_goal_system_blocks`, and analogously in `build_diagnose_messages`): a
   stable block (instructions + lecture content) and a per-goal block. The stable block's
   breakpoint is byte-identical across goals and across concurrent students of the same
   course+model, so a goal switch or a second student re-reads it from cache instead of re-writing
   the whole prefix. `_with_cache_control` marks at most 3 blocks per message (Anthropic allows 4
   breakpoints/request; the latest message uses one).
2. **Cheap diagnose model** — the learning-goals diagnose call (IID-LEARN-DIAGNOSE) is internal,
   non-streamed JSON whose input is dominated by lecture content; `llm.diagnose_model` routes it to
   a cheap model (default `google/gemini-3-flash-preview`) independent of the tutor model.
Motivation: a two-day exam-prep burst (2026-07-14/15, 17 students, ~1,100 assistant turns on
Sonnet 5) cost ≈ $40, ~94% of it input tokens from re-sending lecture content on every call.
**Success criteria:**
- No visible change for students; a failed/ignored cache marker degrades to full-price tokens,
  never to an error.
- Cache reads appear in OpenRouter activity (cache discount > 0) for Anthropic models.
**Key files:** `src/llm_client.py` (`_with_cache_control`, applied in `stream_response` +
`complete_json`), `config.yaml` (`llm.diagnose_model`), `src/course_loader.py` (merge),
`src/tutor_loop.py` (`diagnose_answer` model override).
**No-Goals:** RAG/chunking (see IID-RAG-RETRIEVAL), trimming lecture content, provider-specific
cache TTL tuning, caching for the test harness (`tests/` passes messages through unchanged paths
and benefits automatically).

## Core Mode: Eval

### IID-EVAL-FEEDBACK
**Lifecycle:** TODO
**Description:** Eval mode — bot reviews the student's chat history or a submitted answer and produces qualitative feedback plus a grade.
**Inputs:**
- `chat_history` or `submission` (text): student work to evaluate.
- `rubric` (optional): educator-supplied grading criteria.
**Outputs:**
- `feedback` (Markdown): qualitative comments on strengths and weaknesses.
- `grade` (string/number): score or letter grade with justification.
**Success criteria:**
- Feedback is specific, references lecture content.
- Grade is consistent with rubric when provided.
- Student can share comment/critique.

## Admin / Educator Tools

### IID-CHAT-VIEW
**Lifecycle:** DONE
**Description:** Local HTML viewer for educator review of student sessions and feedback. Reads all `exports/sheets_backup_*.csv` files (produced by IID-SHEETS-LOG), deduplicates across files, and writes `exports/chats.html` — a single self-contained file. Left panel lists sessions (newest first) with email, turn count, and feedback badge. Right panel renders the full conversation with Markdown + LaTeX (marked.js + KaTeX via CDN). Feedback entries show the student comment and the flagged AI message (collapsible).
**Key files:** `scripts/render_chats.py`
**CLI:** `python scripts/render_chats.py` → `exports/chats.html`
**No-Goals:** Live/real-time view, server-side hosting, search across sessions.

### IID-EDUCATOR-CONFIG
**Lifecycle:** v1
**Description:** Educator-facing configuration: 
    - upload lecture content folder, 
    - config file for: course name, choose active mode(s), configure LLM parameters, valid login domains 
    - folder of chat history
    - folder for student feedback
    - `content/_system_prompt.md`: editable LLM behaviour instructions (role, rules, tone)
    - `content/_welcome.md`: editable first chat message shown to students
    - `chainlit.md`: editable sidebar/welcome panel description (Chainlit root, not in content/)
    - convention: `_`-prefixed files in `content/` are app-config, excluded from lecture content injection
    - multi-course: each non-`_` subfolder of `content/` is a course; `_meta.yaml` configures name, description, and optional LLM overrides (see IID-MULTI-COURSE)
**Inputs:** Config UI or config file.
**Outputs:** Persisted course configuration used at runtime.
**No-Goals:** Multi-tenant SaaS management console

### IID-MULTI-COURSE
**Lifecycle:** IN_PROGRESS
**Description:** Multi-course support via `content/` subfolders. Each non-`_`-prefixed subfolder is a separate course. `_meta.yaml` (required: `lecture_name`; optional: `description`, `order`, `model`, `temperature`, `max_tokens`, `first_date`, `last_date`) configures it. At startup, `src/course_loader.py` discovers courses; Chainlit's `@cl.set_chat_profiles` presents a profile chooser when courses exist. Courses outside their availability window are hidden from the chooser. Falls back to existing single-course behavior when no subfolders are present.
**Fallback chain:**
- `_system_prompt.md`: subfolder → `content/` root
- `_welcome.md`: subfolder → `content/` root
- `model` / `temperature` / `max_tokens`: `_meta.yaml` → `config.yaml` llm section
- `lecture_name` / `{{course_name}}`: `_meta.yaml.lecture_name` → `config.yaml.course_name`

**Shared content:** optional `extra_content` list in `_meta.yaml` — file paths relative to the
content root, injected *before* the course's own folder content (see `load_files` in
`src/content_loader.py`). Lets several courses include one shared file without duplication;
convention: put shared files in `content/_shared/` (the `_` prefix keeps it out of course
discovery). Missing listed file or non-list value → loud SystemExit naming the folder.
Used by the three Q&A part courses (`qna_part1/2/3`), which each cover one part of the lecture
scripts and all share `_shared/script0.qmd` (intro + syllabus); their `_system_prompt.md` lists
all three parts so the bot redirects students to the right part.
**`_meta.yaml` format:**
```yaml
lecture_name: "Course Name"          # required; shown in profile chooser
description: "Markdown description"  # optional; rendered in profile chooser
order: 1                             # optional; sort order in chooser (default 999)
model: "google/gemini-3-flash-preview"  # optional LLM override
temperature: 0.3                         # optional LLM override
max_tokens: 2048                         # optional LLM override
first_date: 2026-05-01               # optional; inclusive lower bound (server local date)
last_date:  2026-05-15               # optional; inclusive upper bound (server local date)
extra_content:                       # optional; shared files (relative to content/ root),
  - _shared/script0.qmd              #   injected before the course's own folder content
student_model_choices:               # optional; IID-STUDENT-MODEL-CHOICE
  - id: "google/gemini-3-flash-preview"
    label: "Gemini Flash"
  - id: "openai/gpt-4o-mini"
    label: "GPT-4o Mini"
```
**Success criteria:**
- When multiple course subfolders exist, a profile chooser appears and each course loads its own content and config.
- When no subfolders exist, behavior is identical to single-course v1 behavior.
- Missing `_meta.yaml` or missing `lecture_name` → loud startup failure (SystemExit) naming the offending folder.
- Missing `_system_prompt.md` or `_welcome.md` in a subfolder silently uses the root fallback.
- A course is hidden from the profile chooser when `first_date` is in the future or `last_date` is in the past (server local date, both inclusive). When at least one date is set, an "Available …" line is appended to the course description in the chooser.
- Invalid date format or `first_date > last_date` → loud SystemExit naming the folder and field.
**Key files:** `src/course_loader.py` (new), `app.py`
**No-Goals:** Per-course auth rules, per-course Google Sheet routing, nested course folder hierarchies, hour/timezone-precise availability windows, per-student access overrides.

### IID-STUDENT-MODEL-CHOICE
**Lifecycle:** DONE
**Description:** Per-course educator-defined list of LLM models students can choose from during a session. Configured via `student_model_choices` in `_meta.yaml` (list of `{id, label}` entries). When set, Chainlit's Chat Settings gear exposes a model dropdown; changes apply from the next message. The active model is stored in every assistant log entry (JSONL `model` field + Google Sheet `model` column) and displayed as a chip below assistant bubbles in the HTML chat viewer. Inactive when `student_model_choices` is absent or empty.
**Key files:** `src/course_loader.py` (`CourseConfig` field + parsing), `src/chat_logger.py` (`model` column), `app.py` (`on_chat_start` ChatSettings + `on_settings_update`), `scripts/render_chats.py` (model chip)

---

## Data storage and management

### IID-CHAT-LOG
**Lifecycle:** v1
**Description:** Every chat session is logged to a local file for the educator to review. Each log entry records: session ID (anonymous UUID), timestamp, role (user/assistant), and message content. Logs are written to a `logs/` folder as newline-delimited JSON (one file per session).
**Standards:** SID-PRIVACY-DATA
**Inputs:** Each chat turn (user message + assistant response).
**Outputs:** `logs/<session-id>.jsonl` files.
**Success criteria:**
- Every message in every session is persisted before the next turn begins.
- Educator can open log files without special tooling (plain JSONL).
- When IID-AUTH-BASIC is active, `user_email` is included in each log entry; absent otherwise.
**No-Goals:** Database storage, search/query UI over logs — those are v2.

### IID-SHEETS-LOG
**Lifecycle:** DONE
**Description:** Optional persistent logging of all chat turns to a Google Sheet, surviving Railway redeploys. Supplements IID-CHAT-LOG (JSONL remains as local fallback). Each row records: timestamp, session_id, role, content. Authentication uses a service account key stored as the `GOOGLE_SERVICE_ACCOUNT_JSON` Railway environment variable. Enabled by setting `sheets_log_id` in `config.yaml`; disabled (no-op) when blank.
**Standards:** SID-PRIVACY-DATA
**Inputs:** Each chat turn (user message + assistant response).
**Outputs:** Rows appended to `sheet1` of the configured Google Sheet.
**Success criteria:**
- Writes are non-blocking (fire-and-forget via thread executor) — no added latency to student chat.
- Failures (network, quota) print a warning to stderr and do not crash the app.
- Header row is auto-inserted on first write to an empty sheet.
**No-Goals:** Reading back logs via the app, multi-sheet routing, PII enrichment.

### IID-STUDENT-FEEDBACK-STORE
**Lifecycle:** DONE
**Description:** Collect and store per-message student feedback events. A 🚩 flag button is attached to each AI response. Clicking it prompts the student for free-text feedback via `cl.AskUserMessage`. Feedback is appended to the same per-session JSONL (`logs/<session_id>.jsonl`) with `role="feedback"`, `content=<student comment>`, and `flagged_message=<AI response>`. Also appended to the Google Sheet (IID-SHEETS-LOG) as a new row with a `flagged_message` column (6th column).
**Key files:** `app.py` (`@cl.on_action("flag")`), `src/chat_logger.py` (`log_feedback`)

## Login

### IID-AUTH-BASIC
**Lifecycle:** DONE
**Description:** Minimal authentication: student login via email restricted to configured domains / individual addresses. First login = automatic self-registration (student picks their own password). Educator configures `auth.allowed_domains` and `auth.allowed_emails` in `config.yaml`. If both lists are empty, auth is disabled and app is public. Registered users stored in `users.yaml` (gitignored, bcrypt-hashed passwords). User email is captured in session state and included in all log entries (IID-CHAT-LOG, IID-SHEETS-LOG).
**Key files:** `src/auth.py`, `config.yaml` (auth section), `users.yaml` (runtime, gitignored), `app.py` (`@cl.password_auth_callback`)
**Setup:** Generate JWT secret with `chainlit create-secret`, add as `CHAINLIT_AUTH_SECRET` in `.env` and Railway variables.
**Password reset:** Educator removes student entry from `users.yaml`; student re-registers on next login.
**No-Goals:** SSO, OAuth, institutional LDAP integration, email verification, password strength enforcement

---

### IID-MULTIMODE-ROUTER
**Lifecycle:** TODO
**Description:** UI mode switcher allowing a student to select QA / Learn / Eval. Routes the chat session to the appropriate IID handler. Educator can restrict available modes per course.

---

### IID-RAG-RETRIEVAL
**Lifecycle:** v2
**Description:** Retrieval-augmented generation pipeline: embed the student query, retrieve top-k chunks from the vector store (IID-LECTURE-INGEST), inject into LLM context window. Replaces IID-CONTENT-INJECT for larger corpora.
**Success criteria:**
- Retrieval latency < 500 ms for typical course corpus (< 500 pages)

---

### IID-SESSION-HISTORY
**Lifecycle:** CANDO
**Description:** Persist chat history per student per session so students can resume interrupted conversations.
**Standards:** SID-PRIVACY-DATA
**No-Goals:** Cross-device sync for v1.

---

### IID-EXPORT-TRANSCRIPT
**Lifecycle:** CANDO
**Description:** Allow student to download a PDF/Markdown transcript of their chat session or of lessons learned

---

## Testing

### IID-TEST-SMOKE
**Lifecycle:** DONE
**Description:** Deployment health check for the live Railway app. Two levels: (1) HTTP ping — GET the live URL and assert HTTP 2xx; (2) Playwright chat simulation — send a real question via headless browser and assert a response arrives. Level 1 runs in GitHub Actions CI on every push to master. Level 2 runs on-demand locally.
**Inputs:** Live Railway URL (`LIVE_URL` in `tests/smoke.py`).
**Outputs:** Exit code 0 (pass) or 1 (fail). CI job fails if the HTTP ping fails.
**Key files:** `tests/smoke.py`, `.github/workflows/ci.yml`

### IID-TEST-LLM-EVAL
**Lifecycle:** DONE
**Description:** Evaluate LLM pipeline quality without deployment — directly calls `src/content_loader` and `src/llm_client`, bypassing Chainlit. Test cases are defined in YAML files (`tests/cases/`) so educators can add/edit them without touching Python. An LLM-as-judge grades each response against a per-case rubric (PASS/FAIL + explanation). The judge model defaults to the same model in `config.yaml`; override with `JUDGE_MODEL` env var for a stronger grader.
**Inputs:** `tests/cases/*.yaml` (question + rubric per case), `config.yaml`, `.env`.
**Outputs:** PASS/FAIL verdict + explanation printed per case; full results in `reports/` via compare.py.
**Key files:** `tests/runner.py`, `tests/judge.py`, `tests/cases/qna.yaml`, `tests/cases/behavior.yaml`
**Learning-goals extension (IID-LEARN-GOALS):** `tests/learn_goals.py` is a multi-turn harness that, per goal,
judges (a) the tutor's opening question against a `question_rubric` and (b) the tutor's feedback to live
student-simulator personas against per-persona `feedback_rubric`s. Cases in `tests/cases/learn_part1_goals.yaml`.
Degrades to an ERROR verdict (not a crash) when the judge model returns empty; `JUDGE_MODEL` overrides the grader.
**CLI:**
- `python tests/runner.py --cases tests/cases/qna.yaml` — run cases, print responses
- `python tests/runner.py --case <id> --judge` — run single case with judge verdict
- `python tests/runner.py --dry-run` — validate config + content without LLM calls

### IID-TEST-MODEL-COMPARE
**Lifecycle:** DONE
**Description:** Run the same test cases through multiple model/prompt variants (defined in `tests/configs/variants.yaml`) and write a side-by-side comparison table to `reports/compare_<timestamp>.md`. Variants can differ in model, temperature, max_tokens, or system prompt. Reports are gitignored and generated locally on demand.
**Inputs:** `tests/configs/variants.yaml` (model variants), `tests/cases/*.yaml` (test cases).
**Outputs:** `reports/compare_<timestamp>.md` — markdown table with Case, Variant, Model, Verdict, Explanation columns plus a summary of PASS rates per variant.
**Key files:** `tests/compare.py`, `tests/configs/variants.yaml`
**CLI:** `python tests/compare.py` (uses all default cases and variants)
