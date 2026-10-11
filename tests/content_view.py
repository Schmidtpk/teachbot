"""
IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK, IID-CONTENT-FROM-HTML,
IID-TEST-LLM-EVAL
Offline tests for the HTML viewer panel: indexing slide decks / card graphs / plain pages,
the page context the bot gets, answer links, the window-message handler, the file route,
HTML text as lecture content (`content_from_viewer`), and that a course WITHOUT HTML
behaves exactly as before.

No network, no LLM. Small HTML fixtures are written to a temp folder. The app is imported
with config_timeseries.yaml, whose card course needs the (gitignored) HTML copied in by
scripts/sync_timeseries.py; the real files are then indexed too as a sanity check.

Run:  .venv\\Scripts\\python tests/content_view.py
"""

import asyncio
import contextlib
import io
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("TEACHBOT_CONFIG", "config_timeseries.yaml")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

import app  # noqa: E402
from src.course_loader import (  # noqa: E402
    build_system_prompt, build_viewer, discover_courses, load_course_content,
)
from src.viewer_docs import (  # noqa: E402
    CARDGRAPH, GENERIC, REVEAL, ViewerSet, detect_kind, load_viewer_docs, read_doc,
)

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


def exits(fn) -> bool:
    try:
        fn()
    except SystemExit:
        return True
    return False


class FakeSession:
    """Stands in for cl.user_session."""

    def __init__(self, **kw) -> None:
        self._d = dict(kw)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value) -> None:
        self._d[key] = value


# A Quarto reveal.js deck, reduced to what matters: sections with ids, a level-1 section
# title, MathJax-delimited math, a figure, speaker notes and a script that must be dropped.
DECK = """<!DOCTYPE html><html><head><title>Univariate Time Series Analysis</title>
<style>.x{color:red}</style></head><body><div class="reveal"><div class="slides">
<section id="title-slide" class="quarto-title-block center"><h1 class="title">Univariate Time Series Analysis</h1>
<p class="subtitle">Ch. 3 – ARMA Models<br><br>HS 2026</p></section>
<section id="the-ar1-process" class="title-slide slide level1 center"><h1>The AR(1) process</h1></section>
<section id="ar1-def" class="slide level2"><h2>Autoregressive processes: AR(1)</h2>
<p>The model <span class="math inline">\\(y_t = \\phi y_{t-1} + e_t\\)</span> with
<span class="math display">\\[\\rho(k) = \\phi^k\\]</span></p>
<aside class="notes"><p>SECRET LECTURER NOTE</p></aside>
<script>var leaked = "SCRIPT TEXT";</script></section>
<section id="ar1-plot" class="slide level2"><h2>Autoregressive processes: AR(1), <span class="math inline">\\(\\phi = 0.9\\)</span></h2>
<pre><code>set.seed(0)
  y &lt;- arima.sim(model = list(ar = 0.9), n = 120)</code></pre>
<p><img src="data:image/png;base64,AAAA" alt=""></p></section>
<section id="where-next" class="slide level2"><h2>Where next</h2><p>MA processes.</p></section>
</div></div></body></html>"""

# The ../graph viewer: card data as JSON in <script id="data">. Edge source = card used.
CARDS = """<!DOCTYPE html><html><head><title>Time Series Cards</title></head><body>
<script id="data" type="application/json">{"cards": {
 "white-noise": {"title": "white noise", "type": "definition", "introduced": 1.01,
   "summary": "Uncorrelated, mean zero.", "html": "<p>A sequence <span class=\\"math inline\\">e_t</span> is white noise.</p>",
   "subfiles": [], "key_concepts": [], "generalizes": [], "special_of": [],
   "backlinks": ["ar1-process"], "sources": ["01-intro.qmd: White noise"]},
 "ar1-process": {"title": "AR(1) process", "type": "definition", "introduced": 1.02,
   "summary": "The process <span class=\\"math inline\\">y_t = \\\\phi y_{t-1} + e_t</span>.",
   "html": "<p>Defined with <a class=\\"card-link\\" data-id=\\"white-noise\\">white noise</a>.</p>",
   "subfiles": [{"name": "details", "label": "Details", "html": "<p>More detail.</p>"}],
   "key_concepts": ["white-noise"], "generalizes": [], "special_of": ["ghost-card"],
   "backlinks": [], "sources": ["deck.qmd: Autoregressive processes: AR(1) (basic properties)"]}
}, "edges": [{"source": "white-noise", "target": "ar1-process", "kind": "key"}]}</script>
</body></html>"""

PAGE = """<html><head><title>Course syllabus</title></head><body><nav>menu</nav>
<h1>Syllabus</h1><p>Exam on 1 February.</p></body></html>"""


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="lectos_viewer_"))
    course = tmp / "course"
    course.mkdir()
    (course / "deck.html").write_text(DECK, encoding="utf-8")
    (course / "cards.html").write_text(CARDS, encoding="utf-8")
    (course / "syllabus.html").write_text(PAGE, encoding="utf-8")
    (course / "_private.html").write_text(PAGE, encoding="utf-8")

    # 1 — detection and indexing
    print("case: reading the three kinds of document")
    check(detect_kind(DECK) == REVEAL, "reveal.js deck detected")
    check(detect_kind(CARDS) == CARDGRAPH, "card graph detected")
    check(detect_kind(PAGE) == GENERIC, "anything else is a generic page")

    deck = read_doc(course / "deck.html")
    check(deck.label == "Ch. 3 – ARMA Models",
          f"deck label from the subtitle, not the shared <title> (got {deck.label!r})")
    check(deck.order == ["title-slide", "the-ar1-process", "ar1-def", "ar1-plot", "where-next"],
          f"one location per slide, in order (got {deck.order})")
    s = deck.locations["ar1-def"]
    check(s.section == "The AR(1) process", f"slide knows its section (got {s.section!r})")
    check("$y_t = \\phi y_{t-1} + e_t$" in s.text and "$$\\rho(k) = \\phi^k$$" in s.text,
          "MathJax \\( \\) and \\[ \\] become $ / $$ (the forms the chat renders)")
    check("SECRET LECTURER NOTE" not in s.text, "speaker notes are dropped")
    check("SCRIPT TEXT" not in s.text, "scripts are dropped")
    p = deck.locations["ar1-plot"]
    check(p.title == "Autoregressive processes: AR(1), $\\phi = 0.9$",
          f"slide title with math (got {p.title!r})")
    check("  y <- arima.sim" in p.text, "code keeps its indentation and entities are decoded")
    check("[figure]" in p.text, "an image becomes a [figure] marker, never base64")

    cards = read_doc(course / "cards.html")
    c = cards.locations["ar1-process"]
    check(cards.label == "Time Series Cards", "card graph label from <title>")
    check(c.relations["builds on (key concepts)"] == ["white-noise"], "key concepts kept")
    check(c.relations["is a special case of"] == [], "links to cards that do not exist are dropped")
    check("More detail." in c.text and "## Details" in c.text, "subfiles are part of the card text")
    check(cards.locations["white-noise"].relations["used by"] == ["ar1-process"], "backlinks kept")

    page = read_doc(course / "syllabus.html")
    check(page.order == [""] and "Exam on 1 February." in page.locations[""].text,
          "generic page = one location holding its text")
    check("menu" not in page.locations[""].text, "navigation chrome is dropped")

    # 2 — which files a course shows
    print("\ncase: which files are shown")
    docs = load_viewer_docs(course, None, "test")
    check([d.doc_id for d in docs] == ["cards", "deck", "syllabus"],
          f"default: every non-_ .html, sorted (got {[d.doc_id for d in docs]})")
    check(load_viewer_docs(course, False, "test") == [], "`viewer: false` turns it off")
    picked = load_viewer_docs(course, [{"file": "deck.html", "label": "Slides"}, "cards.html"], "test")
    check([(d.doc_id, d.label) for d in picked] == [("deck", "Slides"), ("cards", "Time Series Cards")],
          "explicit list: these files, this order, optional labels")
    check(exits(lambda: load_viewer_docs(course, [{"file": "missing.html"}], "test")),
          "a listed file that does not exist stops startup")
    check(exits(lambda: load_viewer_docs(course, "deck.html", "test")),
          "a malformed `viewer` value stops startup")
    plain = tmp / "plain"
    plain.mkdir()
    (plain / "notes.md").write_text("# Notes", encoding="utf-8")
    check(build_viewer(plain, None, "plain", "test") is None,
          "a folder without HTML has no viewer (None), so nothing changes")

    # 3 — addressing and links
    print("\ncase: addressing, links")
    vs = ViewerSet(docs, "/viewer/course")
    check(vs.url("deck", "ar1-def") == "/viewer/course/deck.html#/ar1-def", "reveal fragment is #/id")
    check(vs.url("cards", "white-noise") == "/viewer/course/cards.html#white-noise", "card fragment is #id")
    check(vs.validate("deck", "nope") == ("deck", ""), "unknown slide → start of the deck")
    check(vs.validate("../app", "x") is None and vs.validate(None, None) is None,
          "unknown document → rejected")
    check(vs.parse_href("/viewer/course/deck.html#/ar1-plot/2") == ("deck", "ar1-plot"),
          "reveal's fragment index (#/id/2) is ignored")
    check(vs.parse_href("/viewer/other/deck.html#/ar1-def") is None, "another course's link is rejected")
    check(vs.parse_href(42) is None, "non-string href rejected")
    text = ("See [the definition](view:cards/ar1-process), [this slide](view:deck/ar1-def), "
            "[a ghost](view:cards/ghost) and [nowhere](view:nodoc/x) and [deck](view:deck).")
    out = vs.rewrite_links(text)
    check("[the definition](/viewer/course/cards.html#ar1-process)" in out, "card link rewritten")
    check("[this slide](/viewer/course/deck.html#/ar1-def)" in out, "slide link rewritten")
    check("a ghost and nowhere" in out and "view:" not in out.replace("[deck](/viewer", ""),
          "invented ids lose the link but keep the text")
    check("[deck](/viewer/course/deck.html)" in out, "a whole-document link works")

    # 4 — slides ↔ cards and the page context
    print("\ncase: page context")
    check(("cards", "ar1-process") in vs.related.get(("deck", "ar1-def"), []),
          "card linked to its slide via `sources` (trailing '(…)' ignored)")
    check(("deck", "ar1-def") in vs.related.get(("cards", "ar1-process"), []),
          "and the slide back to the card")
    ctx = vs.page_context("deck", "ar1-def")
    i_text = ctx.find("$y_t = \\phi y_{t-1} + e_t$")
    i_orient = ctx.find("For orientation only")
    check(ctx.startswith("=== THE STUDENT IS LOOKING AT THIS SLIDE RIGHT NOW ==="),
          "the open slide comes first")
    check(0 < i_text < i_orient, "its full text comes before anything else")
    check("Position: 3 of 5" in ctx and 'section "The AR(1) process"' in ctx, "position and section given")
    check('Previous slide "The AR(1) process"' in ctx and "Next slide" in ctx, "previous and next slide")
    check('Previous slide "The AR(1) process" (view:deck/the-ar1-process)\n' in ctx,
          "a section-title neighbour gets no excerpt (it would only repeat its title)")
    check('card "AR(1) process" (view:cards/ar1-process)' in ctx, "related card with its link id")
    check("$$...$$" in ctx and "never \\(" in ctx, "math-delimiter reminder present")
    cctx = vs.page_context("cards", "ar1-process")
    check(cctx.startswith("=== THE STUDENT IS LOOKING AT THIS CARD") and "Builds on (key concepts):" in cctx,
          "card context: card first, then its key concepts")
    check(vs.marker("deck", "ar1-def") == '[Student had open: Ch. 3 – ARMA Models, slide 3/5 '
          '"Autoregressive processes: AR(1)"]', "one-line history marker")
    check(vs.tag("deck", "ar1-def") == "deck#ar1-def" and vs.tag("syllabus", "") == "syllabus",
          "log tag")
    check(vs.button_word() == "Slides"
          and ViewerSet([cards], "/x").button_word() == "Cards"
          and ViewerSet([page], "/x").button_word() == "Pages",
          "header button word follows the documents (Slides / Cards / Pages)")
    cat = vs.catalog()
    check("DOC deck" in cat and "ar1-def: Autoregressive processes: AR(1)" in cat
          and "white-noise: white noise (definition)" in cat, "catalogue lists linkable ids")

    # 5 — the request copy, never the stored history
    print("\ncase: page context goes into the request only")
    hist = [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}]
    req = app._with_page_context(hist, "CTX")
    check(req[-1]["content"] == "CTX\n\nStudent's message:\nQ", "request carries the context")
    check(hist[-1]["content"] == "Q" and req[0] is hist[0], "stored history untouched")
    check(app._with_page_context(hist, None) is hist, "no open page → the very same history object")

    # 6 — window messages from the browser
    print("\ncase: on_window_message")
    session = FakeSession(viewer=vs, viewer_state={"open": False, "doc": "", "loc": ""})
    app.cl.user_session = session
    run = lambda d: asyncio.run(app.on_window_message(d))  # noqa: E731
    run({"type": "lectos_viewer_state", "open": True, "doc": "deck", "loc": "ar1-plot"})
    check(session.get("viewer_state") == {"open": True, "doc": "deck", "loc": "ar1-plot"},
          "panel state stored")
    run({"type": "lectos_viewer_state", "open": True, "doc": "../../etc/passwd", "loc": "x"})
    check(session.get("viewer_state")["doc"] == "deck", "unknown document ignored")
    run({"type": "lectos_viewer_state", "open": True, "doc": "cards", "loc": "<script>"})
    check(session.get("viewer_state") == {"open": True, "doc": "cards", "loc": ""},
          "unknown location falls back to the document")
    run("lectos_viewer_state")
    run({"type": "something-else"})
    run({"type": "lectos_viewer_available", "count": 3})  # our own echo
    check(session.get("viewer_state")["open"] is True, "strings, unknown types and echoes ignored")
    run({"type": "lectos_viewer_state", "open": False})
    check(session.get("viewer_state")["open"] is False, "closing is recorded")
    app.cl.user_session = FakeSession(viewer=None)
    run({"type": "lectos_viewer_state", "open": True, "doc": "deck", "loc": "ar1-def"})
    check(app.cl.user_session.get("viewer_state") is None, "a course without viewer ignores everything")

    # 7 — the deployed app: route order, Chainlit internals we rely on, no-HTML courses
    print("\ncase: app wiring")
    first = app.chainlit_app.router.routes[0]
    check(getattr(first, "path", "") == "/viewer/{course_id}/{filename}",
          "viewer route sits before Chainlit's catch-all UI route")
    import chainlit
    cl_dir = Path(chainlit.__file__).parent
    sidebar_src = (cl_dir / "sidebar.py").read_text(encoding="utf-8")
    check('"set_sidebar_elements"' in sidebar_src and '"key": key' in sidebar_src,
          "Chainlit still uses the sidebar event app._open_viewer emits")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in (cl_dir / "frontend" / "dist" / "assets").glob("index-*.js"))
    check('title)==="canvas"' in bundle, "Chainlit still has the full-bleed 'canvas' side view")
    check('emit("window_message"' in bundle and 'addEventListener("message"' in bundle,
          "Chainlit still forwards window messages to the server")
    check('"/public/elements/${' in bundle or "/public/elements/" in bundle,
          "Chainlit still loads custom elements from public/elements/")

    no_html = [c for c in discover_courses(ROOT / "content", {"llm": {}}) if c.viewer is None]
    check(len(no_html) > 0, f"courses without HTML have viewer=None ({len(no_html)} in content/)")
    assignment = next((c for c in app.COURSES if c.course_id == "assignment1"), None)
    check(assignment is not None and assignment.viewer is None,
          "timeseries assignment1 (no HTML) has no viewer")
    base = build_system_prompt(assignment)
    check(app._with_viewer_catalog(base, None, "qa") is base,
          "no viewer → the system prompt is exactly the one without this feature")
    check(app._with_viewer_catalog(base, vs, "learning_goals") is base,
          "learning-goals mode keeps its own prompt even with a viewer")
    check(app._with_viewer_catalog(base, vs, "qa").startswith(base)
          and "VIEWER DOCUMENTS START" in app._with_viewer_catalog(base, vs, "qa"),
          "Q&A with a viewer → catalogue appended after the unchanged prompt")

    # 8 — HTML text as the lecture content (IID-CONTENT-FROM-HTML)
    print("\ncase: content_from_viewer")
    root = tmp / "root"

    def course_dir(name: str, meta: str, files: dict[str, str]) -> Path:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "_meta.yaml").write_text(f'lecture_name: "{name}"\n{meta}', encoding="utf-8")
        for fname, text in files.items():
            (d / fname).write_text(text, encoding="utf-8")
        return d

    course_dir("cardsonly", "content_from_viewer: true\n", {"cards.html": CARDS})
    course_dir("paired", "", {"deck.html": DECK, "deck.qmd": "## AR(1)\nqmd text"})
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        found = {c.course_id: c for c in discover_courses(root, {"llm": {}})}
    check("WARNING" not in err.getvalue(), "no warning when every deck has its .qmd")
    cc = found["cardsonly"]
    check(cc.content_from_viewer and cc.viewer is not None, "flag read, viewer built")
    content = load_course_content(cc)
    check('#### Card "AR(1) process" (view:cards/ar1-process) — definition' in content,
          "every card is in the lecture content, with its link id and type")
    check("Summary: The process $y_t = \\phi y_{t-1} + e_t$." in content and "More detail." in content,
          "summary and full text (incl. subfiles) are included")
    check("Related card ids — builds on (key concepts): white-noise" in content
          and "used by" not in content, "outgoing relations as ids; 'used by' left out")
    check("LECTURE CONTENT START" in build_system_prompt(cc) and "white noise" in build_system_prompt(cc),
          "the cards end up in the system prompt")
    paired = found["paired"]
    check(not paired.content_from_viewer and "qmd text" in load_course_content(paired)
          and "Autoregressive" not in load_course_content(paired),
          "without the flag the HTML stays out of the lecture content (the .qmd is it)")

    course_dir("orphan", "", {"deck.html": DECK, "notes.md": "notes"})
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        discover_courses(root, {"llm": {}})
    check("'orphan' shows 'deck.html' but has no 'deck.qmd'" in err.getvalue(),
          "a deck without its .qmd is reported at startup")
    (root / "orphan" / "_meta.yaml").write_text('lecture_name: "o"\ncontent_from_viewer: yes please\n',
                                                 encoding="utf-8")
    check(exits(lambda: discover_courses(root, {"llm": {}})), "a non-boolean flag stops startup")
    (root / "orphan" / "_meta.yaml").write_text('lecture_name: "o"\ncontent_from_viewer: true\nviewer: false\n',
                                                 encoding="utf-8")
    check(exits(lambda: discover_courses(root, {"llm": {}})), "the flag without any HTML stops startup")
    import shutil
    shutil.rmtree(root / "orphan")
    course_dir("empty", "", {"deck.html": DECK})
    with contextlib.redirect_stderr(io.StringIO()):
        empty = next(c for c in discover_courses(root, {"llm": {}}) if c.course_id == "empty")
    check(exits(lambda: load_course_content(empty)),
          "no .qmd and no flag: an empty course still stops startup, as before")

    # 9 — the time series deploy as configured (config_timeseries.yaml)
    print("\ncase: time series courses")
    by_id = {c.course_id: c for c in app.COURSES}
    check([c.course_id for c in app.COURSES] == ["utsa01", "utsa02", "utsa03", "cards", "assignment1"],
          f"one course per chapter, then cards, then the helper (got {list(by_id)})")
    for cid in ("utsa01", "utsa02", "utsa03"):
        c = by_id[cid]
        decks = [d for d in (c.viewer.docs.values() if c.viewer else []) if d.kind == REVEAL]
        check(bool(decks) and all((c.content_dir / f"{d.doc_id}.qmd").is_file() for d in decks)
              and not c.content_from_viewer,
              f"{cid}: decks shown, each with its .qmd as lecture content")
    check([p.name for p in by_id["utsa03"].extra_content]
          == ["script_01-utsa-intro.qmd", "script_02-utsa-fundamentals.qmd"],
          "ch. 3 has the scripts of ch. 1 and 2 as background")
    check(by_id["cards"].content_from_viewer and list(by_id["cards"].viewer.docs) == ["cards"],
          "the card course shows only the cards and answers from them")

    # 10 — the real files (gitignored, copied in by scripts/sync_timeseries.py)
    print("\ncase: real lecture files (local)")
    for c in app.COURSES:
        for d in (c.viewer.docs.values() if c.viewer else []):
            check(len(d.order) > 0 and all(not re.search(r"data:image", d.locations[x].text)
                                           for x in d.order),
                  f"{c.course_id}/{d.filename}: {d.kind}, {len(d.order)} locations, no base64 in text")

    failed = [lbl for ok_, lbl in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED:")
        for lbl in failed:
            print(f"  - {lbl}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
