# Lectos

*an AI Lecturer in Open-Source*

An open-source AI teaching assistant for university courses. Educators drop their lecture content and students can ask questions and receive lecture-based and educator guided answers.

## What it does

| Mode | Status | Description |
|------------------|---------------------|----------------------------------|
| **QA** | ✅ | Students ask questions; the bot answers using lecture content |
| **Learn** | ✅ | Learning-goals practice: The bot goes through a list of learning goals provided by the Educator and asks questions in a Socratic dialog to test and teach |
| **Eval** | 🔜 planned | Bot reviews student work and gives qualitative feedback + grade |

## How it works

At startup, all files in the active course folder are loaded and injected into the LLM system prompt. The model answers strictly from that material, it will say so honestly if a question is outside the course content. Students can 🚩 flag any AI response to send feedback to the educator.

**Multi-course mode:** Place course subfolders under `content/`. Each subfolder is a separate course/section with its own content, system prompt, and LLM config. A profile chooser appears automatically when multiple courses are detected. Courses can be given an availability window (`first_date` / `last_date`), and educators can offer students a choice of LLM models per course.

**Learn mode (learning-goals practice):** Set `mode: learning_goals` in a course's `_meta.yaml` and add a `_learning_goals.yaml`. The bot drills the student through the goals one at a time: It poses a test question, diagnoses each answer (a structured LLM call that credits earlier points and picks the single most important misconception), and gives Socratic feedback until the goal is mastered, at which point the student clicks **✅ Mark goal complete** to move on. Progress persists per student across sessions and redeploys.

**Cost control:** Every request marks the stable prompt prefix (instructions + lecture content) with cache-control breakpoints, so providers with prompt caching (e.g. Anthropic) bill repeated content at a fraction of the input price.

## Quick start

**1. Install dependencies**

``` bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

**2. Configure secrets**

``` bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

Get an API key at [openrouter.ai](https://openrouter.ai).

**3. Add your lecture content**

Place `.qmd` or `.md` files in the `content/` folder. Files prefixed with `_` are app-config (not injected into the LLM).

For **multi-course mode**, create subfolders under `content/` — each needs a `_meta.yaml`:

``` yaml
lecture_name: "Your Course Name"         # required; shown in profile chooser
order: 1                                  # optional; controls sort order
description: "**Markdown** description"  # optional; shown in profile chooser
model: "google/gemini-3-flash-preview"   # optional LLM override
temperature: 0.3
max_tokens: 2048
first_date: 2026-05-01                     # optional; inclusive — hide course before this date
last_date:  2026-05-15                     # optional; inclusive — hide course after this date
mode: learning_goals                       # optional; turns the course into Learn mode
extra_content:                             # optional; shared files (relative to content/ root)
  - _shared/intro.qmd                      #   injected before the course's own folder content
student_model_choices:                     # optional; lets students pick a model via the gear menu
  - id: "google/gemini-3-flash-preview"
    label: "Gemini Flash"
  - id: "openai/gpt-4o-mini"
    label: "GPT-4o Mini"
```

To share one file across several courses (e.g. an intro/syllabus), put it in `content/_shared/` and list it under `extra_content` in each course's `_meta.yaml`.

A `_meta.yaml` at the `content/` root can define a global `student_model_choices` list; courses without their own list fall back to it.

**Availability window:** `first_date` / `last_date` are both optional and inclusive (server local date). A course outside its window is hidden from the profile chooser; when at least one bound is set, an "Available …" line is shown in the chooser.

**Learn mode:** add `mode: learning_goals` to the course's `_meta.yaml` plus a `_learning_goals.yaml`:

``` yaml
goals:
  - id: bayes_rule                     # required, unique, stable (the per-student progress key)
    title: "Bayes' rule"               # optional short label
    goal: "Student can state Bayes' rule and apply it to a numerical example."
    material: |                        # optional: code/formulas/data shown verbatim to the student
      P(A|B) = P(B|A) P(A) / P(B)
```

The diagnostic instructions are editable in `content/_diagnose_prompt.md` (per-course override falls back to the root copy, like `_system_prompt.md`). Progress is stored in a `progress` worksheet of the Google Sheet (`sheets_log_id`) or, without Sheets, in `progress/<email>.json`. Learn mode requires authentication for a stable per-student key.

**4. Configure the course**

Edit `config.yaml`:

``` yaml
course_name: "Your Course Name"
content_dir: content
logs_dir: logs
llm:
  model: anthropic/claude-sonnet-5
  diagnose_model: google/gemini-3-flash-preview  # optional; cheap model for Learn-mode diagnose calls
  temperature: 0.3
  max_tokens: 4096
auth:
  allowed_domains:
    - stud.uni-heidelberg.de   # restrict login to this domain
  allowed_emails:
    - guest@gmail.com          # individual exceptions
```

Set both lists to `[]` to make the app fully public (no login).

**5. Run**

``` bash
.venv\Scripts\python -m chainlit run app.py
```

Open `http://localhost:8000` in a browser.

## Authentication

Students log in with their institutional email as username and a password of their choice. **First login = automatic registration** — no separate sign-up step. Passwords are bcrypt-hashed; plaintext is never stored. To reset a student's password, remove their entry from `users.yaml`.

Requires a JWT secret — generate once:

``` bash
chainlit create-secret
# Add the output as CHAINLIT_AUTH_SECRET in .env
```

## Customising content and behaviour

| File | Purpose |
|-----------------------------|-------------------------------------------|
| `content/_system_prompt.md` | LLM behaviour instructions (role, rules, tone). `{{course_name}}` is substituted per session. |
| `content/_welcome.md` | First chat message shown to students. `{{course_name}}` is substituted. |
| `content/_diagnose_prompt.md` | Learn mode only: diagnostic instructions (structured-JSON output). |
| `chainlit.md` | Sidebar/welcome panel text (Chainlit root). |

Course subfolders can have their own `_system_prompt.md`, `_welcome.md`, and `_diagnose_prompt.md`; missing files fall back to the root `content/` versions.

## Chat logs and educator tools

Every session is written to `logs/<session-id>.jsonl` — plain newline-delimited JSON. If `sheets_log_id` is set in `config.yaml`, turns are also appended to a Google Sheet (useful for Railway deployments where the local filesystem resets on redeploy).

**Local chat viewer:** Reads all `exports/sheets_backup_*.csv` and produces a self-contained HTML file for educator review.

``` bash
python scripts/render_chats.py   # → exports/chats.html
```

**Archive Google Sheet** (download + clear):

``` bash
python scripts/archive_sheet.py  # → exports/sheets_backup_<date>.csv
```

**Download without clearing** and **summarise recent activity**:

``` bash
python scripts/download_sheet.py           # download only, sheet untouched
python scripts/analyze_recent.py --days 14 # per-course/per-student activity summary
```

## Testing

``` bash
# Validate config + content without any LLM calls
python tests/runner.py --dry-run

# Run a single Q&A case with LLM-as-judge verdict
python tests/runner.py --case deterministic_vs_probabilistic --judge

# Run all Q&A cases
python tests/runner.py --cases tests/cases/qna.yaml --judge

# Learn mode: check opening questions + feedback quality (multi-turn harness)
python tests/learn_goals.py

# Side-by-side model/prompt comparison → reports/compare_<timestamp>.md
python tests/compare.py

# Deployment smoke test (HTTP ping)
python tests/smoke.py

# Full smoke test with Playwright browser simulation
python tests/smoke.py --full
```

Add or edit test cases in `tests/cases/*.yaml` — no Python required. Set `JUDGE_MODEL=<model-id>` to grade with a stronger judge than the course model. `tests/learn_goals_report.py` combines one or more `learn_goals.py --json` result files into a single HTML report (verdict table + transcripts).

## Deployment (Railway)

The app deploys automatically on push to `master`. Required Railway environment variables:

| Variable | Purpose |
|--------------------------------------|----------------------------------|
| `OPENROUTER_API_KEY` | LLM access |
| `CHAINLIT_AUTH_SECRET` | JWT secret for student sessions |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account key for Sheets logging (optional) |

``` bash
railway link --project victorious-energy   # link once per machine
railway logs                               # stream runtime logs
railway variables set KEY=value            # set/update a variable
```

## Project structure

```         
lectos/
├── app.py                      # Chainlit entry point
├── config.yaml                 # Course + LLM config
├── .env                        # API secrets — never commit
├── .env.example                # Template for .env
├── railway.toml                # Railway build/deploy settings
├── public/                     # Chainlit branding (logo, favicon, custom.css)
├── content/                    # Lecture files (.qmd, .md)
│   ├── _system_prompt.md       # Default LLM instructions
│   ├── _welcome.md             # Default welcome message
│   ├── _diagnose_prompt.md     # Default Learn-mode diagnostic instructions
│   ├── _meta.yaml              # Optional: global student model list
│   ├── _shared/                # Files shared across courses via extra_content
│   └── <course>/               # Optional course subfolders (multi-course mode)
│       ├── _meta.yaml          # Course name, description, LLM overrides, mode
│       └── _learning_goals.yaml # Learn mode only: goal list
├── logs/                       # Per-session chat logs (JSONL, gitignored)
├── progress/                   # Per-student goal progress (JSON fallback, gitignored)
├── exports/                    # Sheet backups + chat viewer (gitignored)
├── src/
│   ├── content_loader.py       # Reads and cleans content/ at startup
│   ├── course_loader.py        # Discovers course subfolders, merges config
│   ├── goals.py                # Samples a learning goal, builds per-goal prompt
│   ├── tutor_loop.py           # Learn mode two-step turn (diagnose + act)
│   ├── progress_store.py       # Per-student completed-goal store
│   ├── llm_client.py           # OpenRouter async streaming client
│   ├── chat_logger.py          # JSONL + Google Sheets logging
│   └── auth.py                 # Allowlist check, user registry, bcrypt
├── scripts/
│   ├── archive_sheet.py        # Download + clear Google Sheet
│   ├── download_sheet.py       # Download only (sheet untouched)
│   ├── analyze_recent.py       # Activity summary over recent backups
│   └── render_chats.py         # Generate exports/chats.html viewer
├── tests/
│   ├── runner.py               # Run test cases through LLM pipeline
│   ├── judge.py                # LLM-as-judge grader
│   ├── compare.py              # Multi-model comparison
│   ├── learn_goals.py          # Learn-mode multi-turn test harness
│   ├── learn_goals_report.py   # HTML report from learn_goals.py --json results
│   ├── smoke.py                # Deployment health check
│   ├── cases/                  # YAML test cases (qna, behavior, learn goals)
│   └── configs/variants.yaml   # Model/prompt variants for comparison
├── intentions.md               # Feature roadmap and IID tags
└── standards.md                # Cross-cutting coding standards
```

## Stack

- Python 3.11+
- [Chainlit 2.x](https://docs.chainlit.io) — chat UI with Markdown + LaTeX rendering
- [OpenRouter](https://openrouter.ai) — LLM API (`anthropic/claude-sonnet-5` by default; prompt caching enabled where the provider supports it)

## Roadmap

- **v1** — QA mode, content injection, multi-course, authentication, chat logging, student feedback, educator viewer ✅
- **Learn mode** — learning-goals practice with diagnostic Socratic dialogue and per-student progress ✅
- **Next** — Eval mode (graded feedback), a QA/Learn/Eval mode switcher, RAG for large corpora

## Contributing

Issues and PRs welcome. See [intentions.md](intentions.md) for the feature roadmap and [standards.md](standards.md) for coding conventions.

## License

MIT
