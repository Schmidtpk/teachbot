"""
IID-MULTI-COURSE, IID-UI-CONTENT-VIEW, IID-CONTENT-FROM-HTML, SID-CONTENT-RENDER
Copy the time series lecture material into content_timeseries/, one course per chapter.

A deck is always copied as a pair — the `.qmd` (what the bot reads as lecture content) and
the rendered `.html` (what students see in the viewer panel) — so the two cannot drift
apart. Lecture scripts go with their chapter; the card graph (../graph) is its own course.

Sources:
  junctions/lecture_timeseries/slides/   decks (.qmd + rendered .html)
  junctions/lecture_timeseries/script/   lecture scripts (script_*.qmd)
  junctions/lecture_timeseries/exercises/ exercise sheets (with solutions → *_solution.qmd,
                                         gitignored: the repo is public)
  ../graph/site/index.html               card graph → cards/cards.html

Run:
  python scripts/sync_timeseries.py           # copy what changed, list it
  python scripts/sync_timeseries.py --check   # only report; exit 1 if anything differs

Then redeploy: railway up --service teachbot-timeseries --no-gitignore --detach
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LECTURE = ROOT / "junctions" / "lecture_timeseries"
SLIDES = LECTURE / "slides"
SCRIPTS = LECTURE / "script"
EXERCISES = LECTURE / "exercises"
GRAPH = ROOT.parent / "graph" / "site" / "index.html"
TARGET = ROOT / "content_timeseries"

# course folder → decks (file stems in slides/), scripts (in script/), other files.
# `optional_scripts` are copied once they exist (ch. 3 has no script yet).
COURSES: dict[str, dict] = {
    "utsa01": {"decks": ["01-utsa-intro"], "scripts": ["script_01-utsa-intro.qmd"]},
    "utsa02": {"decks": ["02-utsa-fundamentals"], "scripts": ["script_02-utsa-fundamentals.qmd"]},
    "utsa03": {"decks": ["03_1-utsa-arma", "03_2-utsa-arma"],
               "optional_scripts": ["script_03-utsa-arma.qmd"]},
    "cards": {"files": [(GRAPH, "cards.html")]},
    "exercises01-03": {"files": [(EXERCISES / "utsa-exercises-01-03.qmd",
                                  "utsa-exercises-01-03_solution.qmd")]},
}


def plan() -> tuple[list[tuple[Path, Path]], list[str]]:
    """(source, target) pairs to sync, plus problems that stop the sync."""
    pairs: list[tuple[Path, Path]] = []
    problems: list[str] = []
    for course, spec in COURSES.items():
        dest = TARGET / course
        for stem in spec.get("decks", []):
            qmd, html = SLIDES / f"{stem}.qmd", SLIDES / f"{stem}.html"
            for f in (qmd, html):
                if not f.is_file():
                    problems.append(f"missing {f}")
            if qmd.is_file() and html.is_file() and html.stat().st_mtime < qmd.stat().st_mtime:
                problems.append(f"{html.name} is older than {qmd.name} — re-render the deck first")
            pairs += [(qmd, dest / qmd.name), (html, dest / html.name)]
        for name in spec.get("scripts", []):
            src = SCRIPTS / name
            if not src.is_file():
                problems.append(f"missing {src}")
            pairs.append((src, dest / name))
        for name in spec.get("optional_scripts", []):
            src = SCRIPTS / name
            if src.is_file():
                pairs.append((src, dest / name))
            else:
                print(f"  (not yet available: {src.relative_to(LECTURE)})")
        for src, name in spec.get("files", []):
            if not src.is_file():
                problems.append(f"missing {src}")
            pairs.append((src, dest / name))
    return pairs, problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="only report differences")
    args = ap.parse_args()

    if not LECTURE.is_dir():
        sys.exit(f"Source folder not found: {LECTURE} (the junction to the lecture folder).")
    pairs, problems = plan()
    if problems:
        print("Not synced:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    changed = 0
    for src, dst in pairs:
        same = dst.is_file() and filecmp.cmp(src, dst, shallow=False)
        if same:
            continue
        changed += 1
        state = "update" if dst.exists() else "new"
        print(f"  {state:6s} {dst.relative_to(ROOT)}")
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    if not changed:
        print("Everything up to date.")
    elif args.check:
        print(f"{changed} file(s) differ — run without --check to copy them.")
        sys.exit(1)
    else:
        print(f"{changed} file(s) copied. Redeploy: "
              f"railway up --service teachbot-timeseries --no-gitignore --detach")


if __name__ == "__main__":
    main()
