# Lectos
*an AI Lecturer in Open-Source*

An open-source AI teaching assistant for university courses. Educators drop in their lecture content and students get an instant chat interface — grounded in the actual course material.

## What it does

| Mode | Status | Description |
|------|--------|-------------|
| **QA** | ✅ v1 | Students ask questions; the bot answers using lecture content |
| **Learn** | 🔜 planned | Socratic dialogue to guide students through a topic |
| **Eval** | 🔜 planned | Bot reviews student work and gives qualitative feedback + grade |

## How it works

At startup, all files in the active course folder are loaded and injected into the LLM system prompt. The model answers strictly from that material — it will say so honestly if a question is outside the course content. Students can 🚩 flag any AI response to send instant feedback to the educator.

**Multi-course mode:** Place course subfolders under `content/`. Each subfolder is a separate course with its own content, system prompt, and LLM config. A profile chooser appears automatically when multiple courses are detected.

## Quick start

**1. Install dependencies**

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

**2. Configure secrets**

```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

Get an API key at [openrouter.ai](https://openrouter.ai).

**3. Add your lecture content**

Place `.qmd` or `.md` files in the `content/` folder. Files prefixed with `_` are app-config (not injected into the LLM).

For **multi-course mode**, create subfolders under `content/` — each needs a `_meta.yaml`:

```yaml
lecture_name: "Your Course Name"         # required; shown in profile chooser
order: 1                                  # optional; controls sort order
description: "**Markdown** description"  # optional; shown in profile chooser
model: "google/gemini-3-flash-preview"   # optional LLM override
temperature: 0.3
max_tokens: 2048
```

**4. Configure the course**

Edit `config.yaml`:

```yaml
course_name: "Your Course Name"
content_dir: content
logs_dir: logs
llm:
  model: google/gemini-3-flash-preview
  temperature: 0.3
  max_tokens: 2048
auth:
  allowed_domains:
    - stud.uni-heidelberg.de   # restrict login to this domain
  allowed_emails:
    - guest@gmail.com          # individual exceptions
```

Set both lists to `[]` to make the app fully public (no login).

**5. Run**

```bash
.venv\Scripts\python -m chainlit run app.py
```

Open `http://localhost:8000` in a browser.

## Authentication

Students log in with their institutional email as username and a password of their choice. **First login = automatic registration** — no separate sign-up step. Passwords are bcrypt-hashed; plaintext is never stored. To reset a student's password, remove their entry from `users.yaml`.

Requires a JWT secret — generate once:

```bash
chainlit create-secret
# Add the output as CHAINLIT_AUTH_SECRET in .env
```

## Customising content and behaviour

| File | Purpose |
|------|---------|
| `content/_system_prompt.md` | LLM behaviour instructions (role, rules, tone). `{{course_name}}` is substituted per session. |
| `content/_welcome.md` | First chat message shown to students. `{{course_name}}` is substituted. |
| `chainlit.md` | Sidebar/welcome panel text (Chainlit root). |

Course subfolders can have their own `_system_prompt.md` and `_welcome.md`; missing files fall back to the root `content/` versions.

## Chat logs and educator tools

Every session is written to `logs/<session-id>.jsonl` — plain newline-delimited JSON. If `sheets_log_id` is set in `config.yaml`, turns are also appended to a Google Sheet (useful for Railway deployments where the local filesystem resets on redeploy).

**Local chat viewer:** Reads all `exports/sheets_backup_*.csv` and produces a self-contained HTML file for educator review.

```bash
python scripts/render_chats.py   # → exports/chats.html
```

**Archive Google Sheet** (download + clear):

```bash
python scripts/archive_sheet.py  # → exports/sheets_backup_<date>.csv
```

## Testing

```bash
# Validate config + content without any LLM calls
python tests/runner.py --dry-run

# Run a single Q&A case with LLM-as-judge verdict
python tests/runner.py --case deterministic_vs_probabilistic --judge

# Run all Q&A cases
python tests/runner.py --cases tests/cases/qna.yaml --judge

# Side-by-side model/prompt comparison → reports/compare_<timestamp>.md
python tests/compare.py

# Deployment smoke test (HTTP ping)
python tests/smoke.py

# Full smoke test with Playwright browser simulation
python tests/smoke.py --full
```

Add or edit test cases in `tests/cases/*.yaml` — no Python required.

## Deployment (Railway)

The app deploys automatically on push to `master`. Required Railway environment variables:

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | LLM access |
| `CHAINLIT_AUTH_SECRET` | JWT secret for student sessions |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account key for Sheets logging (optional) |

```bash
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
├── content/                    # Lecture files (.qmd, .md)
│   ├── _system_prompt.md       # Default LLM instructions
│   ├── _welcome.md             # Default welcome message
│   └── <course>/               # Optional course subfolders (multi-course mode)
│       └── _meta.yaml          # Course name, description, LLM overrides
├── logs/                       # Per-session chat logs (JSONL, gitignored)
├── exports/                    # Sheet backups + chat viewer (gitignored)
├── src/
│   ├── content_loader.py       # Reads and cleans content/ at startup
│   ├── course_loader.py        # Discovers course subfolders, merges config
│   ├── llm_client.py           # OpenRouter async streaming client
│   ├── chat_logger.py          # JSONL + Google Sheets logging
│   └── auth.py                 # Allowlist check, user registry, bcrypt
├── scripts/
│   ├── archive_sheet.py        # Download + clear Google Sheet
│   └── render_chats.py         # Generate exports/chats.html viewer
├── tests/
│   ├── runner.py               # Run test cases through LLM pipeline
│   ├── judge.py                # LLM-as-judge grader
│   ├── compare.py              # Multi-model comparison
│   ├── smoke.py                # Deployment health check
│   ├── cases/                  # YAML test cases (qna, behavior)
│   └── configs/variants.yaml   # Model/prompt variants for comparison
├── intentions.md               # Feature roadmap and IID tags
└── standards.md                # Cross-cutting coding standards
```

## Stack

- Python 3.11+
- [Chainlit 2.x](https://docs.chainlit.io) — chat UI with Markdown + LaTeX rendering
- [OpenRouter](https://openrouter.ai) — LLM API (`google/gemini-3-flash-preview` by default)

## Roadmap

- **v1** — QA mode, content injection, multi-course, authentication, chat logging, student feedback, educator viewer ✅
- **v2** — Learn mode (Socratic dialogue), Eval mode (graded feedback), RAG for large corpora

## Contributing

Issues and PRs welcome. See [intentions.md](intentions.md) for the feature roadmap and [standards.md](standards.md) for coding conventions.

## License

MIT
