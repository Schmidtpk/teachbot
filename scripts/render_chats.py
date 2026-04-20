"""
IID-SHEETS-LOG, IID-STUDENT-FEEDBACK-STORE
Render all exports/sheets_backup_*.csv files into a single self-contained
HTML viewer: exports/chats.html

Usage:
    python scripts/render_chats.py
"""

import csv
import json
import pathlib
from collections import defaultdict

SCRIPT_DIR = pathlib.Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
EXPORTS_DIR = REPO_DIR / "exports"
OUT_FILE = EXPORTS_DIR / "chats.html"

KNOWN_ROLES = {"user", "assistant", "feedback", "system"}


def normalize_row(row):
    """Handle old-format rows where the user_email column holds the role value.

    Before user_email was added to the logger the columns were:
      timestamp, session_id, role, content, flagged_message
    After, they became:
      timestamp, session_id, user_email, role, content, flagged_message
    Old rows parsed with the new header end up with user_email=role, role=content.
    """
    if row.get("role") in KNOWN_ROLES:
        return row  # new format – correct
    if row.get("user_email") in KNOWN_ROLES:
        return {
            "timestamp": row.get("timestamp", ""),
            "session_id": row.get("session_id", ""),
            "user_email": "",
            "role": row["user_email"],        # actual role
            "content": row.get("role", ""),   # actual content
            "flagged_message": row.get("content", ""),
        }
    return row  # unknown – pass through as-is


def load_sessions():
    csv_files = sorted(EXPORTS_DIR.glob("sheets_backup_*.csv"))
    if not csv_files:
        return []

    seen = set()
    turns = []

    for f in csv_files:
        with open(f, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                row = normalize_row(row)
                # Deduplicate across files
                key = (
                    row.get("timestamp", ""),
                    row.get("session_id", ""),
                    row.get("role", ""),
                    (row.get("content") or "")[:120],
                )
                if key in seen:
                    continue
                seen.add(key)
                if row.get("role") in ("system",):
                    continue  # skip internal test rows
                turns.append(row)

    # Group by session_id
    by_session = defaultdict(list)
    for t in turns:
        by_session[t.get("session_id", "")].append(t)

    # Sort turns within each session by timestamp
    for sid in by_session:
        by_session[sid].sort(key=lambda r: r.get("timestamp", ""))

    # Sort sessions newest-first (by last turn timestamp)
    session_list = sorted(
        by_session.items(),
        key=lambda x: x[1][-1].get("timestamp", ""),
        reverse=True,
    )

    return session_list


def build_session_data(session_list):
    """Convert sessions to a list of dicts for JSON embedding."""
    result = []
    for sid, turns in session_list:
        user_emails = {t["user_email"] for t in turns if t.get("user_email")}
        email = next(iter(user_emails), "anonymous")
        feedback_count = sum(1 for t in turns if t.get("role") == "feedback")
        first_ts = turns[0].get("timestamp", "") if turns else ""
        result.append(
            {
                "id": sid,
                "email": email,
                "timestamp": first_ts,
                "feedback_count": feedback_count,
                "turns": [
                    {
                        "ts": t.get("timestamp", ""),
                        "role": t.get("role", ""),
                        "content": t.get("content", ""),
                        "flagged_message": t.get("flagged_message", ""),
                    }
                    for t in turns
                ],
            }
        )
    return result


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>teachbot – Chat Viewer</title>
<!-- KaTeX CSS (stylesheet only, load early) -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; font-size: 14px;
         display: flex; height: 100vh; background: #f5f5f5; color: #222; }}

  /* ── Sidebar ── */
  #sidebar {{
    width: 280px; min-width: 220px; max-width: 360px;
    background: #1e2533; color: #d0d6e2;
    display: flex; flex-direction: column; overflow: hidden;
  }}
  #sidebar h1 {{ font-size: 13px; font-weight: 600; padding: 14px 16px;
                 background: #161b27; letter-spacing: .05em; color: #8ab4f8; }}
  #session-list {{ overflow-y: auto; flex: 1; }}
  .session-item {{
    padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #2a3145;
    transition: background .15s;
  }}
  .session-item:hover {{ background: #2a3145; }}
  .session-item.active {{ background: #2e4080; }}
  .s-email {{ font-size: 12px; font-weight: 600; color: #8ab4f8;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .s-date  {{ font-size: 11px; color: #8a9ab5; margin-top: 2px; }}
  .s-meta  {{ display: flex; align-items: center; gap: 6px; margin-top: 4px; }}
  .badge   {{ background: #e53935; color: #fff; border-radius: 10px;
              font-size: 10px; padding: 1px 6px; font-weight: 700; }}
  .turns-count {{ font-size: 11px; color: #6a7a95; }}

  /* ── Main ── */
  #main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
  #header {{
    padding: 12px 20px; background: #fff; border-bottom: 1px solid #dde;
    font-size: 13px; color: #555;
  }}
  #header strong {{ color: #222; }}
  #chat-area {{ flex: 1; overflow-y: auto; padding: 20px 24px; }}
  #empty-state {{
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: #999; font-size: 15px;
  }}

  /* ── Messages ── */
  .msg {{ margin-bottom: 14px; display: flex; flex-direction: column; }}
  .msg.user      {{ align-items: flex-end; }}
  .msg.assistant {{ align-items: flex-start; }}
  .msg.feedback  {{ align-items: stretch; }}

  .bubble {{
    max-width: 72%; padding: 10px 16px; border-radius: 12px;
    line-height: 1.6; word-break: break-word; font-size: 13.5px;
  }}
  .msg.user .bubble {{
    background: #1a73e8; color: #fff;
    border-radius: 12px 12px 2px 12px;
  }}
  .msg.assistant .bubble {{
    background: #fff; border: 1px solid #dde;
    border-radius: 12px 12px 12px 2px;
  }}

  /* Markdown content inside bubbles */
  .bubble p  {{ margin: 0 0 .6em; }}
  .bubble p:last-child {{ margin-bottom: 0; }}
  .bubble h1, .bubble h2, .bubble h3 {{ margin: .8em 0 .3em; font-size: 1em; }}
  .bubble ul, .bubble ol {{ margin: .4em 0 .4em 1.4em; }}
  .bubble li {{ margin-bottom: .2em; }}
  .bubble code {{ background: rgba(0,0,0,.08); border-radius: 3px;
                  padding: 1px 4px; font-size: .92em; }}
  .bubble pre  {{ background: rgba(0,0,0,.06); border-radius: 6px;
                  padding: 10px 12px; overflow-x: auto; margin: .5em 0; }}
  .bubble pre code {{ background: none; padding: 0; }}
  /* KaTeX display math */
  .bubble .katex-display {{ margin: .6em 0; overflow-x: auto; }}

  /* User bubble — keep text white over blue */
  .msg.user .bubble code {{ background: rgba(255,255,255,.2); }}
  .msg.user .bubble pre  {{ background: rgba(255,255,255,.15); }}

  .msg-ts {{ font-size: 10px; color: #aaa; margin-top: 3px; padding: 0 4px; }}

  /* ── Feedback block ── */
  .feedback-block {{
    background: #fffbe6; border: 1px solid #f9a825; border-radius: 10px;
    padding: 12px 16px;
  }}
  .feedback-label  {{ font-size: 11px; font-weight: 700; color: #b45309; margin-bottom: 6px; }}
  .feedback-comment {{ font-size: 13px; color: #333; margin-bottom: 8px; }}
  .flagged-toggle {{
    font-size: 11px; color: #777; cursor: pointer; user-select: none;
    display: inline-flex; align-items: center; gap: 4px;
  }}
  .flagged-toggle::before {{ content: "▶ "; font-size: 9px; }}
  .flagged-toggle.open::before {{ content: "▼ "; }}
  .flagged-body {{
    display: none; margin-top: 8px; padding: 10px 14px; background: #fef3c7;
    border-radius: 6px; font-size: 12px; color: #444;
    border-left: 3px solid #f9a825;
  }}
  .flagged-body p {{ margin: 0 0 .5em; }}
  .flagged-body p:last-child {{ margin-bottom: 0; }}
</style>
</head>
<body>

<div id="sidebar">
  <h1>teachbot · Chats</h1>
  <div id="session-list"></div>
</div>

<div id="main">
  <div id="header"><span id="header-text">Select a session</span></div>
  <div id="chat-area">
    <div id="empty-state">← Select a session to view the conversation</div>
  </div>
</div>

<!-- KaTeX JS and marked.js loaded synchronously before inline script -->
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@9.1.6/lib/marked.umd.min.js"></script>
<script>
const SESSIONS = {sessions_json};

/* ── Rendering ── */

function fmtDate(iso) {{
  if (!iso) return "";
  try {{ return new Date(iso).toLocaleString(undefined, {{dateStyle:"short",timeStyle:"short"}}); }}
  catch {{ return iso; }}
}}

function escHtml(s) {{
  return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}}

/**
 * Render markdown + LaTeX into a DOM element.
 *
 * Strategy: extract all math spans ($...$ and $$...$$) BEFORE handing
 * text to marked.js, replace with unique placeholders, render markdown,
 * then substitute back with katex.renderToString().
 * This prevents marked from mangling LaTeX (e.g. _x_ → <em>x</em>).
 */
function renderMd(text, el) {{
  const stash = [];

  function stashMath(math, display) {{
    const id = "MATHSTASH" + stash.length + "X";
    stash.push({{ math, display }});
    return id;
  }}

  // Protect display math $$...$$ (possibly multiline)
  let s = (text || "").replace(/\$\$([\s\S]*?)\$\$/g, (_, m) => stashMath(m, true));
  // Protect inline math $...$  (single line, not empty)
  s = s.replace(/\$([^\\$\\n]+?)\$/g, (_, m) => stashMath(m, false));

  // Render markdown (marked is synchronous)
  let html = marked.parse(s);

  // Restore math with KaTeX
  html = html.replace(/MATHSTASH(\d+)X/g, (_, i) => {{
    const entry = stash[+i];
    try {{
      return katex.renderToString(entry.math, {{
        displayMode: entry.display,
        throwOnError: false,
        trust: false,
      }});
    }} catch(e) {{
      return escHtml(entry.math);
    }}
  }});

  el.innerHTML = html;
}}

/* ── Session list ── */

function buildSessionList() {{
  const list = document.getElementById("session-list");
  SESSIONS.forEach((sess, idx) => {{
    const el = document.createElement("div");
    el.className = "session-item";
    el.dataset.idx = idx;
    const badge = sess.feedback_count > 0
      ? `<span class="badge">&#9873; ${{sess.feedback_count}}</span>` : "";
    const turns = sess.turns.filter(t => t.role === "user" || t.role === "assistant").length;
    el.innerHTML = `
      <div class="s-email">${{escHtml(sess.email)}}</div>
      <div class="s-date">${{fmtDate(sess.timestamp)}}</div>
      <div class="s-meta">${{badge}}<span class="turns-count">${{turns}} turns</span></div>`;
    el.addEventListener("click", () => loadSession(idx, el));
    list.appendChild(el);
  }});
}}

/* ── Conversation view ── */

function loadSession(idx, el) {{
  document.querySelectorAll(".session-item").forEach(e => e.classList.remove("active"));
  el.classList.add("active");

  const sess = SESSIONS[idx];
  document.getElementById("header-text").innerHTML =
    `<strong>${{escHtml(sess.email)}}</strong> &mdash; ${{fmtDate(sess.timestamp)}}`;

  const area = document.getElementById("chat-area");
  const empty = document.getElementById("empty-state");
  if (empty) empty.remove();
  area.innerHTML = "";

  sess.turns.forEach(turn => {{
    const div = document.createElement("div");
    div.className = "msg " + turn.role;

    if (turn.role === "feedback") {{
      const hasFlag = (turn.flagged_message || "").trim();

      // Outer structure
      div.innerHTML = `
        <div class="feedback-block">
          <div class="feedback-label">&#9873; Student feedback</div>
          <div class="feedback-comment"></div>
          ${{hasFlag
            ? `<span class="flagged-toggle">Flagged message</span>
               <div class="flagged-body"></div>`
            : ""}}
        </div>
        <div class="msg-ts">${{fmtDate(turn.ts)}}</div>`;

      renderMd(turn.content || "(no comment)", div.querySelector(".feedback-comment"));
      if (hasFlag) renderMd(turn.flagged_message, div.querySelector(".flagged-body"));

      const toggle = div.querySelector(".flagged-toggle");
      if (toggle) {{
        toggle.addEventListener("click", () => {{
          toggle.classList.toggle("open");
          const body = toggle.nextElementSibling;
          if (body) body.style.display = toggle.classList.contains("open") ? "block" : "none";
        }});
      }}

    }} else {{
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      renderMd(turn.content, bubble);

      const ts = document.createElement("div");
      ts.className = "msg-ts";
      ts.textContent = fmtDate(turn.ts);

      div.appendChild(bubble);
      div.appendChild(ts);
    }}

    area.appendChild(div);
  }});

  area.scrollTop = 0;
}}

buildSessionList();
</script>
</body>
</html>
"""


def main():
    session_list = load_sessions()
    if not session_list:
        print("No sheets_backup_*.csv files found in", EXPORTS_DIR)
        return

    data = build_session_data(session_list)
    sessions_json = json.dumps(data, ensure_ascii=False, indent=2)

    html = HTML_TEMPLATE.format(sessions_json=sessions_json)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_FILE} ({len(data)} sessions)")


if __name__ == "__main__":
    main()
