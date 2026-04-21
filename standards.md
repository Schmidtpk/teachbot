# standards.md — Lectos

Cross-cutting standards that apply across the codebase. Each standard has a unique SID tag.
Reference SIDs in code comments wherever a snippet must adhere to a standard. See also: intentions.md.

---

### SID-STACK (v1)
The application is built with **Python + Chainlit** as the UI and server framework. Chainlit provides streaming chat, Markdown/LaTeX rendering, and session management out of the box. No R/Shiny.
- Minimum Python version: 3.11
- Dependency management: `pyproject.toml` or `requirements.txt` pinned to exact versions.

---

### SID-LLM-PROVIDER (v1)
All LLM calls go through **OpenRouter** using an OpenAI-compatible API client. The model for v1 is `google/gemini-3-flash-preview` (large context window, low cost). Model string, base URL, and API key are never hardcoded — see SID-API-CONFIG.
- Switch models by changing the model string in config only; no code changes required.

---

### SID-API-CONFIG (v1)
LLM provider, model name, temperature, and token limits are configured via a single config file (`config.yaml`) or environment variables. No API keys appear in source code or version control. `.env` is gitignored.

---

### SID-CONTENT-RENDER (CANDO)
`.qmd` and `.md` content files are pre-rendered to HTML at app startup for display in the UI (IID-UI-CONTENT-VIEW).
- Quarto auto-generates section anchor IDs (e.g. `#sec-equilibrium`) — the LLM can reference these in responses as fragment links.

---

### SID-PRIVACY-DATA (v1)
- v1 logs chat content (session ID as anonymous UUID, timestamps, messages) to local `logs/` JSONL files. No names, emails, or IP addresses are stored in v1.
- `logs/` folder is gitignored — never committed to version control.
- Educator is responsible for securing the logs folder on the host machine.
- v2 will revisit data retention policy when authentication (IID-AUTH-BASIC) is added.

---
