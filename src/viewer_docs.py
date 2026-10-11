"""
IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK, SID-CONTENT-RENDER
Pre-rendered HTML documents shown next to the chat, and what the bot knows about them.

A course folder may hold `*.html` files (Quarto reveal.js decks, a knowledge-card graph
built by ../graph, or any other page). They are indexed once at startup into *locations*
(a slide, a card, or the whole page) with plain text, so that:

  * the viewer panel can tell the server where the student is (doc + location id),
  * the bot gets that location's text, prominently, plus its neighbours before answering
    (IID-UI-CONTENT-CONTEXT),
  * the bot can point to pages with `[text](view:DOC/LOC)` links, rewritten into real
    panel links after streaming (IID-UI-CONTENT-MARK).

The HTML files are never injected whole: a Quarto deck is ~7 MB, almost all base64 images.
Without any HTML in a folder nothing here is used and the app behaves exactly as before.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Kinds of document, detected from the HTML itself (no configuration needed).
REVEAL = "reveal"        # Quarto / reveal.js slide deck: one location per slide
CARDGRAPH = "cardgraph"  # ../graph viewer: <script id="data"> JSON with `cards`
GENERIC = "generic"      # anything else: the whole page is one location

# Budgets for the per-turn page context (characters). The current page is given in full up
# to CURRENT_MAX; everything around it is deliberately short so it cannot drown the page the
# student is actually looking at.
CURRENT_MAX = 15000
NEIGHBOUR_EXCERPT = 500
GENERIC_MAX = 30000
MAX_RELATED = 8
CATALOG_MAX = 400


@dataclass
class Location:
    """IID-UI-CONTENT-CONTEXT: one addressable place in a document (slide, card, page)."""
    loc_id: str
    title: str
    text: str
    section: str = ""   # reveal: title of the enclosing level-1 section
    summary: str = ""   # cardgraph: the card's one-line summary
    ctype: str = ""     # cardgraph: definition | theorem | example | ...
    # cardgraph: relation name -> card ids, e.g. {"key concepts": [...], "used by": [...]}
    relations: dict[str, list[str]] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)  # cardgraph: "<deck>.qmd: <slide title>"


@dataclass
class ViewerDoc:
    """IID-UI-CONTENT-VIEW: one HTML file of a course, indexed at startup."""
    doc_id: str      # file stem; the DOC in `view:DOC/LOC` links
    filename: str
    path: Path
    label: str       # shown in the panel's document picker and to the bot
    kind: str
    order: list[str]                 # location ids in document order
    locations: dict[str, Location]

    def frag(self, loc_id: str) -> str:
        """URL fragment that makes the page show `loc_id` (reveal uses `#/id`)."""
        if not loc_id:
            return ""
        return f"#/{loc_id}" if self.kind == REVEAL else f"#{loc_id}"

    def noun(self) -> str:
        return {REVEAL: "slide", CARDGRAPH: "card"}.get(self.kind, "page")


# ---------------------------------------------------------------------------------------
# HTML → text
# ---------------------------------------------------------------------------------------

_BLOCK = {"p", "div", "section", "li", "ul", "ol", "tr", "table", "pre", "blockquote",
          "figure", "figcaption", "dl", "dt", "dd", "br", "hr", "h1", "h2", "h3", "h4",
          "h5", "h6"}
_SKIP = {"script", "style", "noscript", "template", "svg", "button", "nav"}


class _Text(HTMLParser):
    """Plain-text extraction that keeps what a tutor needs: headings, lists, code, math
    (as LaTeX source) and a marker where a figure is. Speaker notes (`aside.notes`) are
    lecturer-only and dropped. With `slides=True`, text is collected per reveal.js slide.
    """

    def __init__(self, slides: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.slides = slides
        self.skip_depth = 0
        self.skip_stack: list[str] = []
        self.pre = 0
        self.math: list[list[Any]] = []   # stack of [display?, parts]
        self.out: list[str] = []          # page mode
        # slide mode
        self.slide_stack: list[dict | None] = []
        self.slide_list: list[dict] = []
        self.heading: dict | None = None

    # -- helpers ---------------------------------------------------------------------
    def _cur(self) -> list[str] | None:
        if not self.slides:
            return self.out
        for s in reversed(self.slide_stack):
            if s is not None:
                return s["parts"]
        return None

    def _emit(self, text: str) -> None:
        if self.math:
            self.math[-1][1].append(text)
            return
        if self.heading is not None:
            self.heading["title"].append(text)
        cur = self._cur()
        if cur is not None:
            cur.append(text)

    # -- parser callbacks ------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        classes = a.get("class", "").split()
        if self.skip_depth:
            if tag == self.skip_stack[-1]:
                self.skip_depth += 1
            return
        if tag in _SKIP or (tag == "aside" and "notes" in classes):
            self.skip_stack.append(tag)
            self.skip_depth = 1
            return
        if self.slides and tag == "section":
            if a.get("id") and ("slide" in classes or a["id"] == "title-slide"):
                s = {"id": a["id"], "parts": [], "title": "",
                     "level1": "level1" in classes}
                self.slide_stack.append(s)
                self.slide_list.append(s)
            else:
                self.slide_stack.append(None)
            return
        if tag == "span" and "math" in classes:
            self.math.append(["display" in classes, []])
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._emit("\n\n" + "#" * int(tag[1]) + " ")
            if self.slides and self.heading is None:
                self.heading = {"title": [], "tag": tag}
            return
        if tag == "li":
            self._emit("\n- ")
            return
        if tag == "pre":
            self.pre += 1
            self._emit("\n```\n")
            return
        if tag == "img":
            alt = a.get("alt", "").strip()
            self._emit(f" [figure: {alt}] " if alt else " [figure] ")
            return
        if tag in ("td", "th"):
            self._emit(" | ")
            return
        if tag in _BLOCK:
            self._emit("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            if tag == self.skip_stack[-1]:
                self.skip_depth -= 1
                if not self.skip_depth:
                    self.skip_stack.pop()
            return
        if self.slides and tag == "section":
            if self.slide_stack:
                self.slide_stack.pop()
            return
        if tag == "span" and self.math:
            display, parts = self.math.pop()
            self._emit(_dollar_math("".join(parts).strip(), display))
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self.heading is not None and self.heading["tag"] == tag:
                for s in reversed(self.slide_stack):
                    if s is not None:
                        if not s["title"]:
                            s["title"] = _squash("".join(self.heading["title"]))
                        break
                self.heading = None
            self._emit("\n")
            return
        if tag == "pre":
            self.pre = max(0, self.pre - 1)
            self._emit("\n```\n")
            return
        if tag in _BLOCK:
            self._emit("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self._emit(data if self.pre else re.sub(r"\s+", " ", data))


def _dollar_math(tex: str, display: bool) -> str:
    """Math as `$…$` / `$$…$$`, whatever the HTML used (MathJax `\\(…\\)`, `\\[…\\]`, or
    bare KaTeX source). The model copies the delimiters it sees, and only the dollar forms
    render in the chat (IID-UI-RENDER) — `\\(` loses its backslash in markdown."""
    for left, right in (("\\(", "\\)"), ("\\[", "\\]"), ("$$", "$$"), ("$", "$")):
        if tex.startswith(left) and tex.endswith(right) and len(tex) >= len(left) + len(right):
            display = display or left in ("\\[", "$$")
            tex = tex[len(left):len(tex) - len(right)].strip()
            break
    return f"$${tex}$$" if display else f"${tex}$"


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _tidy(text: str) -> str:
    lines = [ln.rstrip() for ln in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_text(html: str) -> str:
    """IID-UI-CONTENT-CONTEXT: readable plain text of an HTML fragment or page."""
    p = _Text()
    p.feed(html)
    p.close()
    return _tidy("".join(p.out))


# ---------------------------------------------------------------------------------------
# Readers, one per kind of document
# ---------------------------------------------------------------------------------------

_CARD_DATA = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)


def detect_kind(html: str) -> str:
    """IID-UI-CONTENT-VIEW: which reader understands this HTML."""
    m = _CARD_DATA.search(html)
    if m:
        try:
            if isinstance(json.loads(m.group(1)).get("cards"), dict):
                return CARDGRAPH
        except (ValueError, AttributeError):
            pass
    if re.search(r'<div class="reveal[" ]', html) and 'class="slides' in html:
        return REVEAL
    return GENERIC


def _first(pattern: str, html: str) -> str:
    m = re.search(pattern, html, re.S | re.I)
    return _squash(unescape(re.sub(r"<[^>]+>", " ", m.group(1)))) if m else ""


def _reveal_label(html: str) -> str:
    """'Univariate Time Series Analysis' is the same for every deck — the subtitle
    ('Ch. 1 – Introduction <br> HS 2026 …') is what tells them apart."""
    m = re.search(r'<p class="subtitle"[^>]*>(.*?)</p>', html, re.S)
    if m:
        first = re.split(r"<br\s*/?>", m.group(1))[0]
        label = _squash(unescape(re.sub(r"<[^>]+>", " ", first)))
        if label:
            return label
    return _first(r"<title>(.*?)</title>", html)


def _read_reveal(html: str) -> tuple[str, list[str], dict[str, Location]]:
    p = _Text(slides=True)
    p.feed(html)
    p.close()
    order: list[str] = []
    locs: dict[str, Location] = {}
    section = ""
    for s in p.slide_list:
        text = _tidy("".join(s["parts"]))
        title = s["title"] or ("Title slide" if s["id"] == "title-slide" else s["id"])
        if s["level1"] and s["id"] != "title-slide":
            section = title
        if s["id"] in locs:  # ids are unique in Quarto output; keep the first if not
            continue
        order.append(s["id"])
        locs[s["id"]] = Location(loc_id=s["id"], title=title, text=text,
                                 section="" if s["level1"] else section)
    return _reveal_label(html), order, locs


def _read_cardgraph(html: str) -> tuple[str, list[str], dict[str, Location]]:
    data = json.loads(_CARD_DATA.search(html).group(1))
    cards: dict = data["cards"]
    # `edges`: source = the card that is used, target = the card that uses it
    linked_from: dict[str, list[str]] = {}
    for e in data.get("edges") or []:
        if e.get("kind") == "link":
            linked_from.setdefault(e.get("target"), []).append(e.get("source"))

    def _ids(raw: Any) -> list[str]:
        return [x for x in (raw or []) if isinstance(x, str) and x in cards]

    order = sorted(cards, key=lambda cid: (float(cards[cid].get("introduced") or 0), cid))
    locs: dict[str, Location] = {}
    for cid in order:
        c = cards[cid]
        parts = [html_to_text(c.get("html", ""))]
        for sub in c.get("subfiles") or []:
            sub_text = html_to_text(sub.get("html", ""))
            if sub_text:
                parts.append(f"## {sub.get('label') or sub.get('name') or 'More'}\n\n{sub_text}")
        key = _ids(c.get("key_concepts"))
        uses = [x for x in _ids(linked_from.get(cid)) if x not in key]
        locs[cid] = Location(
            loc_id=cid,
            title=str(c.get("title") or cid),
            text=_tidy("\n\n".join(p for p in parts if p)),
            summary=html_to_text(c.get("summary", "")),
            ctype=str(c.get("type") or ""),
            relations={
                "builds on (key concepts)": key,
                "also uses": uses,
                "generalizes": _ids(c.get("generalizes")),
                "is a special case of": _ids(c.get("special_of")),
                "used by": _ids(c.get("backlinks")),
            },
            sources=[s for s in c.get("sources") or [] if isinstance(s, str)],
        )
    label = _first(r"<title>(.*?)</title>", html) or "Cards"
    return label, order, locs


def _read_generic(html: str) -> tuple[str, list[str], dict[str, Location]]:
    label = _first(r"<title>(.*?)</title>", html)
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    text = html_to_text(body.group(1) if body else html)
    return label, [""], {"": Location(loc_id="", title=label, text=text)}


_READERS = {REVEAL: _read_reveal, CARDGRAPH: _read_cardgraph, GENERIC: _read_generic}


def read_doc(path: Path, label: str | None = None) -> ViewerDoc:
    """IID-UI-CONTENT-VIEW: index one HTML file. Raises on unreadable input."""
    html = path.read_text(encoding="utf-8", errors="replace")
    kind = detect_kind(html)
    auto_label, order, locs = _READERS[kind](html)
    return ViewerDoc(doc_id=path.stem, filename=path.name, path=path,
                     label=label or auto_label or path.stem, kind=kind,
                     order=order, locations=locs)


def load_viewer_docs(folder: Path, spec: Any, where: str) -> list[ViewerDoc]:
    """IID-UI-CONTENT-VIEW: the documents a course shows next to the chat.

    `spec` is the optional `viewer` value of the course's `_meta.yaml`:
      * absent  → every non-`_` `*.html` in the folder, sorted by file name;
      * `false` → no viewer for this course;
      * a list of `{file, label?}` (or bare file names) → exactly these, in this order.
    No HTML files → [] and the course behaves exactly as without this feature.
    Invalid spec or unreadable file → loud startup failure naming `where`.
    """
    if spec is False:
        return []
    entries: list[tuple[Path, str | None]] = []
    if spec is None:
        entries = [(p, None) for p in sorted(folder.glob("*.html")) if not p.name.startswith("_")]
    elif isinstance(spec, list):
        for e in spec:
            if isinstance(e, str):
                e = {"file": e}
            if not isinstance(e, dict) or not isinstance(e.get("file"), str):
                sys.exit(f"[Lectos] ERROR: 'viewer' in {where} must be a list of "
                         f"{{file, label}} entries — got {e!r}.")
            p = folder / e["file"]
            if p.suffix.lower() != ".html" or not p.is_file():
                sys.exit(f"[Lectos] ERROR: 'viewer' in {where} lists '{e['file']}', "
                         f"but '{p}' is not an existing .html file.")
            entries.append((p, str(e["label"]) if e.get("label") else None))
    else:
        sys.exit(f"[Lectos] ERROR: 'viewer' in {where} must be false or a list of files.")

    docs: list[ViewerDoc] = []
    for p, label in entries:
        try:
            docs.append(read_doc(p, label))
        except Exception as exc:  # noqa: BLE001 — any parse problem stops the deploy
            sys.exit(f"[Lectos] ERROR: cannot read viewer file '{p}' ({where}): {exc}")
    ids = [d.doc_id for d in docs]
    if len(set(ids)) != len(ids):
        sys.exit(f"[Lectos] ERROR: viewer files in {where} share a file stem: {ids}.")
    return docs


# ---------------------------------------------------------------------------------------
# The set of documents of one course: links, catalogue, per-turn context
# ---------------------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Loose key for matching slide titles across .qmd source and rendered HTML."""
    s = s.lower().replace("\\phi", "phi").replace("\\theta", "theta")
    return re.sub(r"[^a-z0-9]+", "", s)


_VIEW_LINK = re.compile(r"\[([^\]\n]+)\]\(view:([A-Za-z0-9_.\-]+)(?:/([^\s)]*))?\)")


class ViewerSet:
    """IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK: one course's documents."""

    def __init__(self, docs: list[ViewerDoc], url_prefix: str) -> None:
        self.docs: dict[str, ViewerDoc] = {d.doc_id: d for d in docs}
        self.url_prefix = url_prefix.rstrip("/")
        self.related: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self._link_slides_and_cards()

    def __bool__(self) -> bool:
        return bool(self.docs)

    # -- cross references ------------------------------------------------------------
    def _link_slides_and_cards(self) -> None:
        """Cards record their slide as `sources: ["03_1-utsa-arma.qmd: <slide title>"]`.
        Matching that title against the deck of the same file stem links each slide to
        the cards made from it, and each card back to its slides."""
        by_title: dict[tuple[str, str], list[str]] = {}
        for d in self.docs.values():
            if d.kind == REVEAL:
                for lid in d.order:
                    by_title.setdefault((d.doc_id, _norm(d.locations[lid].title)), []).append(lid)
        for g in self.docs.values():
            if g.kind != CARDGRAPH:
                continue
            for cid in g.order:
                for src in g.locations[cid].sources:
                    deck, _, title = src.partition(":")
                    deck_id = Path(deck.strip()).stem
                    if deck_id not in self.docs:
                        continue
                    title = re.sub(r"\s*\([^()]*\)\s*$", "", title.strip())
                    for sid in by_title.get((deck_id, _norm(title)), []):
                        self._relate((deck_id, sid), (g.doc_id, cid))

    def _relate(self, a: tuple[str, str], b: tuple[str, str]) -> None:
        for x, y in ((a, b), (b, a)):
            lst = self.related.setdefault(x, [])
            if y not in lst:
                lst.append(y)

    # -- addressing ------------------------------------------------------------------
    def url(self, doc_id: str, loc_id: str = "") -> str:
        d = self.docs[doc_id]
        return f"{self.url_prefix}/{d.filename}{d.frag(loc_id)}"

    def validate(self, doc_id: Any, loc_id: Any = "") -> tuple[str, str] | None:
        """(doc, loc) if both exist; unknown loc → doc start; unknown doc → None.
        Everything from the browser goes through here — never trust it as is."""
        if not isinstance(doc_id, str) or doc_id not in self.docs:
            return None
        loc = loc_id if isinstance(loc_id, str) else ""
        return doc_id, loc if loc in self.docs[doc_id].locations else ""

    def parse_href(self, href: Any) -> tuple[str, str] | None:
        """IID-UI-CONTENT-MARK: `/viewer/<course>/<file>#<frag>` → (doc, loc)."""
        if not isinstance(href, str):
            return None
        path, _, frag = href.partition("#")
        if not path.startswith(self.url_prefix + "/"):
            return None
        filename = path[len(self.url_prefix) + 1:]
        doc = next((d for d in self.docs.values() if d.filename == filename), None)
        if doc is None:
            return None
        loc = frag.lstrip("/")
        if doc.kind == REVEAL:
            loc = loc.split("/")[0]  # drop reveal's fragment index (#/id/2)
        return self.validate(doc.doc_id, loc)

    def default_target(self) -> tuple[str, str]:
        first = next(iter(self.docs.values()))
        return first.doc_id, ""

    def client_docs(self) -> list[dict]:
        """IID-UI-CONTENT-VIEW: what the panel needs for its document picker."""
        return [{"id": d.doc_id, "label": d.label, "url": self.url(d.doc_id)}
                for d in self.docs.values()]

    # -- what the bot sees -------------------------------------------------------------
    def describe(self, doc_id: str, loc_id: str) -> str:
        """Short human description, e.g. `Ch. 3.1 – ARMA, slide 7/46 "AR(1)"`."""
        d = self.docs[doc_id]
        if not loc_id or d.kind == GENERIC:
            return d.label
        loc = d.locations[loc_id]
        pos = f" {d.order.index(loc_id) + 1}/{len(d.order)}" if d.kind == REVEAL else ""
        return f'{d.label}, {d.noun()}{pos} "{loc.title}"'

    def tag(self, doc_id: str, loc_id: str) -> str:
        """Compact log value (IID-CHAT-LOG): `03_1-utsa-arma#autoregressive-processes-ar1`."""
        return f"{doc_id}#{loc_id}" if loc_id else doc_id

    def marker(self, doc_id: str, loc_id: str) -> str:
        """One line kept in the chat history instead of the full page context."""
        return f"[Student had open: {self.describe(doc_id, loc_id)}]"

    def _ref(self, doc_id: str, loc_id: str) -> str:
        return f"view:{doc_id}/{loc_id}" if loc_id else f"view:{doc_id}"

    def _brief(self, doc_id: str, loc_id: str, excerpt: bool) -> str:
        d = self.docs[doc_id]
        loc = d.locations[loc_id]
        head = f"- {d.noun()} \"{loc.title}\" ({self._ref(doc_id, loc_id)})"
        if d.kind == CARDGRAPH:
            return f"{head}: {loc.summary}" if loc.summary else head
        if excerpt and loc.text:
            body = _squash(re.sub(r"^#+ [^\n]*\n", "", loc.text))  # title is in `head`
            if len(body) > NEIGHBOUR_EXCERPT:
                body = body[:NEIGHBOUR_EXCERPT].rsplit(" ", 1)[0] + " …"
            return f"{head}: {body}"
        return head

    def page_context(self, doc_id: str, loc_id: str) -> str:
        """IID-UI-CONTENT-CONTEXT: block prepended to the student's message for one request.

        The page the student is looking at comes first and in full; neighbours and related
        cards follow, clearly fenced off as orientation only, so the bot answers about the
        page that is open rather than about whatever is nearby.
        """
        d = self.docs[doc_id]
        loc = d.locations[loc_id]
        text = loc.text
        limit = GENERIC_MAX if d.kind == GENERIC else CURRENT_MAX
        if len(text) > limit:
            text = text[:limit] + "\n[… page text truncated …]"

        lines = [
            f"=== THE STUDENT IS LOOKING AT THIS {d.noun().upper()} RIGHT NOW ===",
            f"Document: {d.label}",
        ]
        if d.kind != GENERIC:
            lines.append(f"{d.noun().capitalize()}: \"{loc.title}\" ({self._ref(doc_id, loc_id)})")
        if d.kind == REVEAL:
            lines.append(f"Position: {d.order.index(loc_id) + 1} of {len(d.order)}"
                         + (f", section \"{loc.section}\"" if loc.section else ""))
        if d.kind == CARDGRAPH and loc.ctype:
            lines.append(f"Type: {loc.ctype}")
        lines += [
            f'"This {d.noun()}", "here", "this", "the plot/formula" in the student\'s message '
            f"refer to it. Figures are marked [figure]; you cannot see them, but the code "
            f"that produced them is usually shown. In your answer, write math as $...$ or "
            f"$$...$$ (never \\( \\) or \\[ \\]).",
            "",
            text or "(no text on this page)",
            f"=== END OF THE {d.noun().upper()} THE STUDENT IS LOOKING AT ===",
        ]

        around: list[str] = []
        if d.kind == REVEAL:
            i = d.order.index(loc_id)
            if i > 0:
                around.append("Previous " + self._brief(doc_id, d.order[i - 1], True)[2:])
            if i + 1 < len(d.order):
                around.append("Next " + self._brief(doc_id, d.order[i + 1], True)[2:])
        if d.kind == CARDGRAPH:
            for rel, ids in loc.relations.items():
                if ids:
                    around.append(f"{rel.capitalize()}:")
                    around += [self._brief(doc_id, x, False) for x in ids[:MAX_RELATED]]
        related = self.related.get((doc_id, loc_id), [])[:MAX_RELATED]
        if related:
            kinds = {self.docs[r[0]].noun() for r in related}
            around.append("Related " + (" and ".join(sorted(kinds))) + "s:")
            around += [self._brief(rd, rl, False) for rd, rl in related]
        if around:
            lines += ["", "--- For orientation only (NOT what the student is looking at) ---",
                      *around, "--- End of orientation ---"]
        return "\n".join(lines)

    def catalog(self) -> str:
        """IID-UI-CONTENT-MARK: system-prompt block listing every linkable page.

        Static per course, so it sits in the cached system prompt; the bot uses it to pick
        cards and slides to point the student to.
        """
        lines = [
            "--- VIEWER DOCUMENTS START ---",
            "Next to the chat, students can open the documents below in a viewer panel. "
            "When pointing the student to a specific slide or card would help (where a "
            "concept is defined, a prerequisite, an example), link it with the markdown "
            "form [link text](view:DOC/LOC) using ONLY the DOC and LOC ids listed here "
            "or in the page context; clicking the link opens it in the panel. Use at most "
            "three such links per answer, and only when they help. Never invent ids.",
        ]
        for d in self.docs.values():
            kind = {REVEAL: "slides", CARDGRAPH: "knowledge cards", GENERIC: "page"}[d.kind]
            lines.append(f"\nDOC {d.doc_id} — {d.label} ({kind}). LOC ids:")
            if d.kind == GENERIC:
                lines.append(f"  (link the whole page as view:{d.doc_id})")
                continue
            for lid in d.order[:CATALOG_MAX]:
                loc = d.locations[lid]
                extra = f" ({loc.ctype})" if loc.ctype else ""
                lines.append(f"  {lid}: {loc.title}{extra}")
        lines.append("--- VIEWER DOCUMENTS END ---")
        return "\n".join(lines)

    def rewrite_links(self, text: str) -> str:
        """IID-UI-CONTENT-MARK: `[t](view:DOC/LOC)` → `[t](/viewer/<course>/<file>#frag)`.
        Unknown targets lose the link but keep the text — never a dead link."""
        def _sub(m: re.Match) -> str:
            hit = self.validate(m.group(2), m.group(3) or "")
            if hit is None or (m.group(3) and hit[1] != m.group(3)):
                return m.group(1)
            return f"[{m.group(1)}]({self.url(*hit)})"
        return _VIEW_LINK.sub(_sub, text)
