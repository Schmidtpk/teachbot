"""
IID-TEST-MODEL-COMPARE, IID-LEARN-GOALS
Combine one or more `tests/learn_goals.py --json` result files into a single self-contained
HTML report: a verdict summary table (checks x models) followed by the full transcripts.

CLI:
    python tests/learn_goals_report.py results/a.json results/b.json --out reports/learn_goals.html
"""

import argparse
import html
import json
from datetime import datetime
from pathlib import Path

_CSS = """
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; max-width: 1100px;
       margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fafafa; line-height: 1.5; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.2rem; margin-top: 2.5rem;
       border-bottom: 2px solid #ddd; padding-bottom: .3rem; }
table { border-collapse: collapse; margin: 1rem 0; width: 100%; background: #fff; }
th, td { border: 1px solid #ddd; padding: .45rem .7rem; text-align: left; font-size: .92rem; }
th { background: #f0f0f0; }
td.v { text-align: center; font-weight: 600; white-space: nowrap; }
.pass { color: #1a7f37; } .fail { color: #c62828; } .error { color: #b26a00; }
details { background: #fff; border: 1px solid #ddd; border-radius: 6px;
          margin: .5rem 0; padding: .5rem .9rem; }
summary { cursor: pointer; font-weight: 600; padding: .25rem 0; }
.msg { white-space: pre-wrap; border-left: 4px solid #ccc; background: #f7f7f7;
       padding: .5rem .8rem; margin: .5rem 0 .9rem; border-radius: 0 4px 4px 0; }
.msg.tutor { border-color: #4a7fb5; } .msg.student { border-color: #8a8a8a; }
.who { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
       color: #666; margin-top: .8rem; }
.verdict { font-size: .88rem; margin: .3rem 0 1rem; }
.meta { color: #666; font-size: .88rem; }
"""

_MARK = {"PASS": ("&#10003; PASS", "pass"), "FAIL": ("&#10007; FAIL", "fail"),
         "ERROR": ("? ERROR", "error")}


def _esc(s: str) -> str:
    return html.escape(s or "")


def _verdict_cell(verdict: str | None) -> str:
    if verdict is None:
        return '<td class="v">—</td>'
    text, cls = _MARK.get(verdict, (verdict, "error"))
    return f'<td class="v {cls}">{text}</td>'


def _summary_table(runs: list[dict]) -> str:
    # collect the union of (goal, check) rows in first-seen order
    rows: list[tuple[str, str]] = []
    for run in runs:
        for rec in run["goals"]:
            for c in rec["checks"]:
                key = (c["goal"], c["check"])
                if key not in rows:
                    rows.append(key)
    if not rows:
        return "<p class='meta'>No judged checks (runs used --no-judge?).</p>"

    lookup = [{(c["goal"], c["check"]): c["verdict"] for rec in run["goals"] for c in rec["checks"]}
              for run in runs]
    out = ["<table><tr><th>goal</th><th>check</th>"]
    out += [f"<th>{_esc(run['model'])}</th>" for run in runs]
    out.append("</tr>")
    for key in rows:
        out.append(f"<tr><td>{_esc(key[0])}</td><td>{_esc(key[1])}</td>")
        out += [_verdict_cell(lk.get(key)) for lk in lookup]
        out.append("</tr>")
    # per-model pass counts
    out.append("<tr><th colspan='2'>PASS rate</th>")
    for lk in lookup:
        n = sum(1 for k in rows if k in lk)
        p = sum(1 for k in rows if lk.get(k) == "PASS")
        out.append(f"<td class='v'>{p}/{n}</td>")
    out.append("</tr></table>")
    return "".join(out)


def _transcripts(runs: list[dict]) -> str:
    out: list[str] = []
    goal_ids: list[str] = []
    for run in runs:
        for rec in run["goals"]:
            if rec["goal"] not in goal_ids:
                goal_ids.append(rec["goal"])
    for gid in goal_ids:
        title = next((rec["title"] for run in runs for rec in run["goals"]
                      if rec["goal"] == gid and rec.get("title")), "")
        out.append(f"<h2>{_esc(gid)}{' — ' + _esc(title) if title else ''}</h2>")
        for run in runs:
            rec = next((r for r in run["goals"] if r["goal"] == gid), None)
            if rec is None:
                continue
            q_check = next((c for c in rec["checks"] if c["check"] == "question"), None)
            state = ""
            if q_check or any("verdict" in t for t in rec["turns"]):
                verdicts = ([q_check["verdict"]] if q_check else []) + \
                           [t["verdict"] for t in rec["turns"] if "verdict" in t]
                bad = sum(v != "PASS" for v in verdicts)
                state = " — all PASS" if bad == 0 else f" — {bad} non-PASS"
            out.append(f"<details><summary>{_esc(run['model'])}{state}</summary>")
            out.append("<div class='who'>Tutor — opening question</div>")
            out.append(f"<div class='msg tutor'>{_esc(rec['question'])}</div>")
            if q_check:
                text, cls = _MARK.get(q_check["verdict"], (q_check["verdict"], "error"))
                out.append(f"<div class='verdict'><span class='{cls}'>{text}</span> "
                           f"{_esc(q_check.get('explanation', ''))}</div>")
            for t in rec["turns"]:
                out.append(f"<div class='who'>Student ({_esc(t['persona'])})</div>")
                out.append(f"<div class='msg student'>{_esc(t['student'])}</div>")
                out.append("<div class='who'>Tutor — feedback</div>")
                out.append(f"<div class='msg tutor'>{_esc(t['feedback'])}</div>")
                if "verdict" in t:
                    text, cls = _MARK.get(t["verdict"], (t["verdict"], "error"))
                    out.append(f"<div class='verdict'><span class='{cls}'>{text}</span> "
                               f"{_esc(t.get('explanation', ''))}</div>")
            out.append("</details>")
    return "".join(out)


def build_report(json_paths: list[Path], out_path: Path) -> None:
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in json_paths]
    course = runs[0].get("course", "?")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = (
        f"<h1>Learning-goals test report — {_esc(course)}</h1>"
        f"<p class='meta'>Generated {stamp} · models: "
        f"{_esc(', '.join(r['model'] for r in runs))} · "
        f"harness: tests/learn_goals.py (IID-TEST-LLM-EVAL, IID-LEARN-GOALS)</p>"
        f"<h2>Summary</h2>{_summary_table(runs)}"
        f"{_transcripts(runs)}"
    )
    doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
           f"<title>learn_goals report — {_esc(course)}</title>"
           f"<style>{_CSS}</style></head><body>{body}</body></html>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    print(f"wrote {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Combine learn_goals JSON results into an HTML report")
    p.add_argument("results", nargs="+", help="JSON files produced by learn_goals.py --json")
    p.add_argument("--out", default=None, help="Output HTML path "
                   "(default: reports/learn_goals_<timestamp>.html)")
    args = p.parse_args()
    out = Path(args.out) if args.out else \
        Path("reports") / f"learn_goals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    build_report([Path(r) for r in args.results], out)


if __name__ == "__main__":
    main()
