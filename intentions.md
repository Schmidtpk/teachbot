# intentions.md — teachbot

Intended functionality of the teachbot codebase. Each intention has a unique IID tag and a lifecycle status.
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
**Description:** At app startup, read all files in `content/`, strip YAML frontmatter and Quarto-specific syntax, concatenate into a single plain-text string, and inject into the LLM system prompt (see SID-LLM-PROVIDER). No vector store or embedding; relies on the model's large context window.
**Inputs:** `content/` folder (`.qmd` files + syllabus).
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

### IID-EDUCATOR-CONFIG
**Lifecycle:** v1
**Description:** Educator-facing configuration: 
    - upload lecture content folder, 
    - config file for: course name, choose active mode(s), configure LLM parameters, valid login domains 
    - folder of chat history
    - folder for student feedback
**Inputs:** Config UI or config file.
**Outputs:** Persisted course configuration used at runtime.
**No-Goals:** Multi-tenant SaaS management console

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
