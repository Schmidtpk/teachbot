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
- No PII beyond message content is stored in v1 (no name, email, IP).
**No-Goals:** Database storage, search/query UI over logs — those are v2.

### IID-STUDENT-FEEDBACK-STORE
**Lifecycle:** TODO
**Description:** Collect and store per-message student feedback events (thumbs up/down, free-text).

## Login

### IID-AUTH-BASIC
**Lifecycle:** v2
**Description:** Minimal authentication: student login via email restricted to a configured domain (e.g. `@university.edu`). v1 is fully public (no auth required).
**No-Goals:** SSO, OAuth, institutional LDAP integration

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
