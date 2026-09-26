"""
IID-WEEKLY-REPORT: weekly e-mail report on the Timeseries chats.

    1. archive   download the "Lectos Timeseries logs" Sheet -> CSV, clear it   (IID-SHEETS-LOG)
    2. prepare   chats.html viewer (IID-CHAT-VIEW) + transcripts.md / flags.md / stats.json
    3. analyse   headless Claude Code agent follows .claude/skills/weekly-report/SKILL.md
                 and writes report_body.html
    4. send      Gmail SMTP: stats + agent report + all student flags verbatim, chats.html attached

Steps 1, 2, 4 are deterministic; if the agent fails, the mail still goes out with the
stats and flags plus an "analysis failed" notice. Output: exports/timeseries/week_<date>/.

Runs once per ISO week (state in exports/timeseries/state.json). A run that stopped
half-way resumes from where it stopped instead of downloading again.

    python scripts/weekly_report.py                 # what Task Scheduler runs (Wednesdays)
    python scripts/weekly_report.py --force         # run again although this week is done
    python scripts/weekly_report.py --keep          # do not clear the Sheet (for trying things out)
    python scripts/weekly_report.py --week-dir exports/timeseries/week_2026-09-30 --no-send
                                                    # re-run the analysis on an existing folder

Needs in .env: GMAIL_USER, GMAIL_APP_PASSWORD (optional REPORT_TO, default GMAIL_USER).
"""

import argparse
import csv
import html
import json
import os
import shutil
import smtplib
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "scripts"))

from archive_sheet import archive  # noqa: E402  IID-SHEETS-LOG
from render_chats import render  # noqa: E402  IID-CHAT-VIEW

CONFIG = REPO_DIR / "config_timeseries.yaml"
OUT_ROOT = REPO_DIR / "exports" / "timeseries"
STATE_FILE = OUT_ROOT / "state.json"
SKILL_FILE = REPO_DIR / ".claude" / "skills" / "weekly-report" / "SKILL.md"
AGENT_MODEL = "opus"
AGENT_TIMEOUT_S = 30 * 60
# The agent's report must contain these section ids (see SKILL.md).
REQUIRED_SECTIONS = ["summary", "tool-problems", "worst-answers", "flags", "focus", "struggles", "suggestions"]


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


# ── State: once per ISO week, resumable ─────────────────────────────────────


def iso_week(d: date | None = None) -> str:
    y, w, _ = (d or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Step 2: agent input files ───────────────────────────────────────────────


def name_from_email(email: str) -> str:
    """firstname.lastname@stud.unibas.ch -> 'Firstname Lastname'."""
    local = email.split("@")[0]
    parts = [p for p in local.replace("_", ".").replace("-", ".").split(".") if p]
    return " ".join(p.capitalize() for p in parts) or email


def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = [{k: (v or "") for k, v in r.items() if k} for r in csv.DictReader(f)]
    rows = [r for r in rows if r.get("role") not in ("system", "")]
    # IID-STREAM-RESILIENCE: before 2026-09-22 a stalled turn was logged as an ordinary
    # assistant row carrying the apology text; count it as the error it was.
    for r in rows:
        if r["role"] == "assistant" and "taking too long to respond" in r.get("content", ""):
            r["role"] = "error"
    return rows


def build_sessions(rows: list[dict], student_domains: list[str]) -> list[dict]:
    by_sid = defaultdict(list)
    for r in rows:
        by_sid[r["session_id"]].append(r)
    sessions = []
    for sid, turns in by_sid.items():
        turns.sort(key=lambda r: r["timestamp"])
        email = next((t["user_email"] for t in turns if t["user_email"]), "")
        sessions.append({
            "session_id": sid,
            "email": email,
            "name": name_from_email(email) if email else "anonymous",
            "is_student": any(email.lower().endswith("@" + d) for d in student_domains),
            "start": turns[0]["timestamp"],
            "end": turns[-1]["timestamp"],
            "turns": turns,
        })
    sessions.sort(key=lambda s: s["start"])
    for i, s in enumerate(sessions, 1):
        s["label"] = f"S{i:02d}"
    return sessions


def fmt_ts(ts: str, with_date: bool = True) -> str:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return ts
    return dt.strftime("%a %d %b %Y %H:%M UTC" if with_date else "%H:%M")


ROLE_TAG = {"user": "STUDENT", "assistant": "TUTOR", "error": "ERROR (student saw an error message)"}


def write_agent_inputs(sessions: list[dict], week_dir: Path) -> dict:
    """transcripts.md, flags.md, stats.json — what the agent reads (not the HTML)."""
    period = (sessions[0]["start"][:10], sessions[-1]["end"][:10])
    flags, t_lines = [], [
        f"# Transcripts — Lectos Timeseries, {period[0]} to {period[1]}",
        "",
        "Session labels (S01, …) are chronological and match stats.json. In chats.html the same",
        "session is found by student e-mail + start time. Accounts marked NON-STUDENT are the",
        "lecturer/tests. Flags are numbered F1, F2, … as in flags.md.",
        "",
    ]
    for s in sessions:
        n_q = sum(t["role"] == "user" for t in s["turns"])
        who = f"{s['name']} ({s['email']})" + ("" if s["is_student"] else " — NON-STUDENT")
        models = sorted({t["model"].split("/")[-1] for t in s["turns"] if t["role"] == "assistant" and t["model"]})
        t_lines += ["", f"## {s['label']} · {who} · {fmt_ts(s['start'])} · {n_q} questions · {', '.join(models)}", ""]
        prev_tutor = ""
        for t in s["turns"]:
            role = t["role"]
            if role == "feedback":
                fid = f"F{len(flags) + 1}"
                flagged = t["flagged_message"] or prev_tutor
                flags.append({"id": fid, "session": s, "ts": t["timestamp"], "comment": t["content"], "flagged": flagged})
                t_lines += [f"### [{fmt_ts(t['timestamp'], False)}] ⚑ FLAG {fid} — student comment:", t["content"] or "(no comment)", ""]
            elif role in ROLE_TAG:
                t_lines += [f"### [{fmt_ts(t['timestamp'], False)}] {ROLE_TAG[role]}", t["content"], ""]
                if role == "assistant":
                    prev_tutor = t["content"]
            # 'diagnosis' rows (learning-goals mode only) are internal and skipped

    f_lines = [f"# Student flags — {len(flags)} this period", ""]
    if not flags:
        f_lines.append("No flags this period.")
    for fl in flags:
        s = fl["session"]
        f_lines += [
            f"## {fl['id']} · {s['label']} · {s['name']} ({s['email']}) · {fmt_ts(fl['ts'])}",
            "",
            "**Student comment:**",
            fl["comment"] or "(no comment)",
            "",
            "**Flagged tutor message:**",
            "",
            *("> " + line for line in (fl["flagged"] or "(not recorded)").splitlines()),
            "",
        ]

    (week_dir / "transcripts.md").write_text("\n".join(t_lines), encoding="utf-8")
    (week_dir / "flags.md").write_text("\n".join(f_lines), encoding="utf-8")

    all_turns = [t for s in sessions for t in s["turns"]]
    students = [s for s in sessions if s["is_student"]]
    q_len = [len(t["content"]) for s in students for t in s["turns"] if t["role"] == "user"]
    a_len = [len(t["content"]) for t in all_turns if t["role"] == "assistant"]
    per_student = Counter(s["email"] for s in students)
    stats = {
        "period": {"first": sessions[0]["start"], "last": sessions[-1]["end"]},
        "sessions": len(sessions),
        "student_sessions": len(students),
        "students": len(per_student),
        "non_student_accounts": sorted({s["email"] for s in sessions if not s["is_student"]}),
        "student_questions": sum(t["role"] == "user" for s in students for t in s["turns"]),
        "tutor_answers": len(a_len),
        "flags": len(flags),
        "errors": sum(t["role"] == "error" for t in all_turns),
        "median_question_chars": int(statistics.median(q_len)) if q_len else 0,
        "median_answer_chars": int(statistics.median(a_len)) if a_len else 0,
        "student_sessions_per_day": dict(sorted(Counter(s["start"][:10] for s in students).items())),
        "models": dict(Counter(t["model"] for t in all_turns if t["role"] == "assistant" and t["model"])),
        "sessions_per_student": {name_from_email(e): n for e, n in per_student.most_common()},
        "session_index": [
            {
                "label": s["label"], "session_id": s["session_id"], "name": s["name"], "email": s["email"],
                "is_student": s["is_student"], "start": s["start"], "end": s["end"],
                "questions": sum(t["role"] == "user" for t in s["turns"]),
                "flags": sum(t["role"] == "feedback" for t in s["turns"]),
                "errors": sum(t["role"] == "error" for t in s["turns"]),
            }
            for s in sessions
        ],
    }
    (week_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    stats["_flags"] = flags  # for the mail appendix only, not written to disk
    return stats


def prepare(csv_path: Path, week_dir: Path) -> dict:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    domains = [d.lower() for d in ((cfg.get("auth") or {}).get("allowed_domains") or [])]
    week_dir.mkdir(parents=True, exist_ok=True)
    render([csv_path], week_dir / "chats.html")
    sessions = build_sessions(load_rows(csv_path), domains)
    stats = write_agent_inputs(sessions, week_dir)
    log(f"Prepared {week_dir.name}: {stats['sessions']} sessions, {stats['flags']} flags")
    return stats


# ── Step 3: the agent ───────────────────────────────────────────────────────


def find_claude() -> str | None:
    # Task Scheduler runs with a thinner PATH than an interactive shell.
    return shutil.which("claude") or next(
        (str(p) for p in [Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude"] if p.exists()),
        None,
    )


def run_agent(week_dir: Path) -> tuple[bool, str]:
    """Headless Claude Code: read-only on the repo, may write only into week_dir."""
    claude = find_claude()
    if not claude:
        return False, "claude CLI not found"
    rel = week_dir.relative_to(REPO_DIR).as_posix()
    body = week_dir / "report_body.html"
    body.unlink(missing_ok=True)
    prompt = (
        f"Read {SKILL_FILE.relative_to(REPO_DIR).as_posix()} and follow it exactly. "
        f"The week folder is {rel}. This is an unattended run: do not ask questions, "
        f"finish by writing {rel}/report_body.html."
    )
    cmd = [
        claude, "-p",
        "--model", AGENT_MODEL,
        "--max-turns", "80",
        "--output-format", "json",
        "--allowedTools", "Read", "Glob", "Grep", f"Write({rel}/**)", f"Edit({rel}/**)",
        "--disallowedTools", "Bash", "PowerShell", "WebFetch", "WebSearch", "Read(.env)", "Read(credentials/**)",
    ]
    log(f"Agent started ({AGENT_MODEL})")
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
            cwd=REPO_DIR, timeout=AGENT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, f"agent timed out after {AGENT_TIMEOUT_S // 60} min"
    (week_dir / "agent_log.json").write_text(proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")

    info = ""
    try:
        res = json.loads(proc.stdout)
        info = f"{res.get('num_turns')} turns, ${res.get('total_cost_usd', 0):.2f}, {res.get('duration_ms', 0) / 60000:.1f} min"
        if res.get("is_error"):
            return False, f"agent error ({res.get('subtype')}): {str(res.get('result'))[:300]}"
    except json.JSONDecodeError:
        return False, f"agent exit code {proc.returncode}: {(proc.stderr or proc.stdout)[:300]}"

    if not body.exists():
        return False, f"agent finished ({info}) but wrote no report_body.html"
    text = body.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if f'id="{s}"' not in text]
    if missing:
        return False, f"report_body.html lacks sections {missing} ({info})"
    log(f"Agent done: {info}")
    return True, info


# ── Step 4: the mail ────────────────────────────────────────────────────────

CSS_BOX = "border:1px solid #ddd;border-radius:6px;padding:10px 14px;margin:8px 0;"


def stats_html(stats: dict) -> str:
    rows = [
        ("Period", f"{stats['period']['first'][:10]} to {stats['period']['last'][:10]}"),
        ("Students / sessions", f"{stats['students']} / {stats['student_sessions']}"),
        ("Student questions", stats["student_questions"]),
        ("Student flags", stats["flags"]),
        ("Error messages shown", stats["errors"]),
        ("Median question / answer length", f"{stats['median_question_chars']} / {stats['median_answer_chars']} chars"),
    ]
    if stats["non_student_accounts"]:
        rows.append(("Non-student accounts (excluded above)", ", ".join(stats["non_student_accounts"])))
    cells = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;color:#666">{html.escape(k)}</td><td><b>{html.escape(str(v))}</b></td></tr>'
        for k, v in rows
    )
    return f'<table style="font-size:14px;border-collapse:collapse;margin-bottom:12px">{cells}</table>'


def flags_html(flags: list[dict]) -> str:
    if not flags:
        return "<p>No flags this period.</p>"
    out = []
    for fl in flags:
        s = fl["session"]
        out.append(
            f'<div style="{CSS_BOX}background:#fffbe6">'
            f"<b>{fl['id']}</b> · {s['label']} · {html.escape(s['name'])} · {fmt_ts(fl['ts'])}<br>"
            f"<b>Comment:</b> {html.escape(fl['comment'] or '(no comment)')}"
            f'<details><summary style="color:#666;font-size:12px">Flagged tutor message</summary>'
            f'<pre style="white-space:pre-wrap;font-size:12px;background:#f7f7f7;padding:8px">{html.escape(fl["flagged"] or "(not recorded)")}</pre>'
            f"</details></div>"
        )
    return "".join(out)


def compose(stats: dict | None, week_dir: Path | None, agent_ok: bool, agent_info: str) -> tuple[str, str]:
    """Returns (subject, html). stats None = no chats this period."""
    if stats is None:
        return "Lectos Timeseries — weekly report: no chats", "<p>No student chats since the last report.</p>"
    period = f"{stats['period']['first'][:10]} – {stats['period']['last'][:10]}"
    subject = f"Lectos Timeseries — weekly report {period}" + ("" if agent_ok else " [analysis failed]")
    if agent_ok:
        analysis = (week_dir / "report_body.html").read_text(encoding="utf-8")
    else:
        analysis = (
            f'<div style="{CSS_BOX}background:#fff4f4;color:#8a2a2a"><b>The analysis agent failed:</b> '
            f"{html.escape(agent_info)}<br>Stats and flags below are complete. Re-run the analysis with<br>"
            f"<code>python scripts/weekly_report.py --week-dir {week_dir.relative_to(REPO_DIR).as_posix()} --force</code></div>"
        )
    footer = (
        f'<p style="color:#888;font-size:12px">Attached: chats.html (all sessions, open in a browser). '
        f"Files: {html.escape(str(week_dir))}. Agent: {html.escape(agent_info)}.</p>"
    )
    body = (
        '<div style="font-family:system-ui,Segoe UI,sans-serif;font-size:14px;line-height:1.5;max-width:860px;color:#222">'
        f"<h2 style=\"margin:0 0 8px\">Lectos Timeseries — week report</h2>{stats_html(stats)}"
        f"{analysis}"
        f'<h3 style="margin-top:28px">Appendix: all student flags, verbatim</h3>{flags_html(stats["_flags"])}'
        f"{footer}</div>"
    )
    return subject, f"<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>{body}</body></html>"


def send_mail(subject: str, html_body: str, attachment: Path | None) -> None:
    load_dotenv(REPO_DIR / ".env")
    user = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = os.environ.get("REPORT_TO", "").strip() or user
    if not user or not password:
        raise SystemExit("ERROR: GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env")

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content("This report is HTML — open it in a mail client that shows HTML.")
    msg.add_alternative(html_body, subtype="html")
    if attachment and attachment.exists():
        msg.add_attachment(attachment.read_bytes(), maintype="text", subtype="html", filename=attachment.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    log(f"Mail sent to {to}: {subject}")


# ── Orchestration ───────────────────────────────────────────────────────────


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="run although this ISO week is already done")
    parser.add_argument("--keep", action="store_true", help="download without clearing the Sheet")
    parser.add_argument("--week-dir", type=Path, help="re-use an existing week folder (skips the download)")
    parser.add_argument("--skip-agent", action="store_true", help="no analysis, stats + flags only")
    parser.add_argument("--no-send", action="store_true", help="write report.html but do not mail it")
    args = parser.parse_args()

    week = iso_week()
    state = load_state()
    # --week-dir / --keep runs are side jobs; they must not touch this week's progress.
    persist = not (args.week_dir or args.keep)
    if state.get("week") == week and state.get("stage") == "sent" and not args.force and persist:
        log(f"{week} already reported — nothing to do (use --force to repeat).")
        return

    # ── 1. archive (or resume) ──
    csv_path: Path | None
    if args.week_dir:
        week_dir = (REPO_DIR / args.week_dir).resolve() if not args.week_dir.is_absolute() else args.week_dir
        csv_path = next(iter(sorted(week_dir.glob("sheets_backup_*.csv"))), None)
        if not csv_path:
            raise SystemExit(f"ERROR: no sheets_backup_*.csv in {week_dir}")
    elif persist and state.get("week") == week and state.get("stage") in ("archived", "prepared", "analysed") and state.get("csv"):
        csv_path, week_dir = Path(state["csv"]), Path(state["week_dir"])
        log(f"Resuming {week} from stage '{state['stage']}' ({week_dir.name})")
    else:
        from archive_sheet import sheet_id_from_config

        week_dir = OUT_ROOT / f"week_{date.today():%Y-%m-%d}"
        csv_path, _ = archive(sheet_id_from_config(CONFIG), week_dir, clear=not args.keep)
        state = {"week": week, "week_dir": str(week_dir), "csv": str(csv_path) if csv_path else "", "stage": "archived"}
        if persist:
            save_state(state)
        if csv_path is None:
            if not args.no_send:
                send_mail(*compose(None, None, False, ""), None)
            if persist:
                save_state({**state, "stage": "sent"})
            return

    def advance(stage: str) -> None:
        if persist:
            state.update(stage=stage)
            save_state(state)

    # ── 2. prepare ──
    stats = prepare(csv_path, week_dir)
    advance("prepared")

    # ── 3. analyse ──
    if args.skip_agent:
        agent_ok, agent_info = False, "skipped (--skip-agent)"
    else:
        agent_ok, agent_info = run_agent(week_dir)
        if not agent_ok:
            log(f"Agent FAILED: {agent_info}")
    advance("analysed")

    # ── 4. send ──
    subject, body = compose(stats, week_dir, agent_ok, agent_info)
    (week_dir / "report.html").write_text(body, encoding="utf-8")
    if args.no_send:
        log(f"--no-send: report written to {week_dir / 'report.html'}")
        return
    send_mail(subject, body, week_dir / "chats.html")
    advance("sent")


if __name__ == "__main__":
    main()
