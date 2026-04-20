# teachbot

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

- Project: `victorious-energy` on Railway, service: `teachbot`
- Live URL: https://teachbot-production-2e85.up.railway.app
- Deploys automatically on push to `master` via GitHub connection

```bash
# Link project (once per machine, after railway login)
railway link --project victorious-energy

# Check deployment status
railway deployment list

# Stream runtime logs
railway logs

# Stream build logs
railway logs --build

# Set/update an environment variable
railway variables set KEY=value

# Trigger a manual redeploy
railway redeploy --yes
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

## Key files

| File | IID/SID | Description |
|------|---------|-------------|
| `app.py` | IID-CHAT-SHELL1, IID-QNA-CORE, IID-AUTH-BASIC | Chainlit entry point |
| `config.yaml` | IID-EDUCATOR-CONFIG, SID-API-CONFIG | Course + LLM config |
| `requirements.txt` | SID-STACK | Pinned dependencies |
| `.env` | SID-API-CONFIG | API secrets — gitignored, never commit |
| `.env.example` | SID-API-CONFIG | Template for .env |
| `content/_system_prompt.md` | IID-EDUCATOR-CONFIG, IID-QNA-CORE | Editable LLM behaviour instructions; `{{course_name}}` substituted at startup |
| `content/_welcome.md` | IID-EDUCATOR-CONFIG, IID-CHAT-SHELL1 | Editable first chat message shown to students; `{{course_name}}` substituted at startup |
| `chainlit.md` | IID-EDUCATOR-CONFIG | Editable sidebar/welcome panel (Chainlit requires it at project root) |
| `src/content_loader.py` | IID-CONTENT-INJECT | Loads + cleans `content/` folder; skips `_`-prefixed files (app-config convention) |
| `src/llm_client.py` | SID-LLM-PROVIDER | OpenRouter async streaming client |
| `src/chat_logger.py` | IID-CHAT-LOG, IID-SHEETS-LOG | Writes `logs/<uuid>.jsonl` per session; appends rows to Google Sheet if `sheets_log_id` set |
| `src/auth.py` | IID-AUTH-BASIC | Allowlist check, user load/save, bcrypt hash/verify |
| `users.yaml` | IID-AUTH-BASIC | Runtime user registry (gitignored, auto-created on first registration) |
| `credentials/` | IID-SHEETS-LOG | Gitignored folder for Google service account JSON key |
| `scripts/archive_sheet.py` | IID-SHEETS-LOG | Downloads Sheet → `exports/sheets_backup_<date>.csv`, then clears it |
| `scripts/archive_sheet.bat` | IID-SHEETS-LOG | Windows Task Scheduler wrapper for the archive script |
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
```

**Test case authoring:** Add/edit cases in `tests/cases/*.yaml` — no Python required.
Each case needs an `id`, `question`, `rubric`, and optional `tags`.
`reports/` is gitignored; comparison reports are local only.
