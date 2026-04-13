# teachbot

An open-source AI teaching assistant for university courses. Educators drop in their lecture content and students get an instant chat interface — grounded in the actual course material.

## What it does

| Mode | Status | Description |
|------|--------|-------------|
| **QA** | v1 | Students ask questions; the bot answers using lecture content |

## How it works

At startup, all files in `content/` are loaded and injected into the LLM system prompt. The model answers strictly from that material — it will say so honestly if a question is outside the course content.

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

Get a API key at [openrouter.ai](https://openrouter.ai).

**3. Add your lecture content**

Place `.qmd` or `.md` files in the `content/` folder. A `syllabus.md` is a good starting point.

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
```

**5. Run**

```bash
.venv\Scripts\python -m chainlit run app.py
```

Open `http://localhost:8000` in a browser.

## Project structure

```
teachbot/
├── app.py                 # Chainlit entry point
├── config.yaml            # Course + LLM config (edit this)
├── .env                   # API secrets — never commit
├── .env.example           # Template for .env
├── content/               # Your lecture files (.qmd, .md)
├── logs/                  # Per-session chat logs (JSONL)
├── src/
│   ├── content_loader.py  # Reads and cleans content/ at startup
│   ├── llm_client.py      # OpenRouter async streaming client
│   └── chat_logger.py     # Writes logs/<uuid>.jsonl per session
├── intentions.md          # Feature roadmap and IID tags
└── standards.md           # Cross-cutting coding standards
```

## Chat logs

Every session is written to `logs/<session-id>.jsonl` — plain newline-delimited JSON, readable without special tooling. No PII beyond message content is stored.

## Stack

- Python 3.11+
- [Chainlit 2.x](https://docs.chainlit.io) — chat UI with Markdown + LaTeX rendering
- [OpenRouter](https://openrouter.ai) — LLM API (`google/gemini-3-flash-preview` by default)

## Roadmap

- **v1** — QA mode, content injection, chat logging ✓
- **v2** — Learn mode (Socratic dialogue), Eval mode (graded feedback), RAG for large corpora, email-domain login

## Contributing

Issues and PRs welcome. See [intentions.md](intentions.md) for the feature roadmap and [standards.md](standards.md) for coding conventions.

## License

MIT
