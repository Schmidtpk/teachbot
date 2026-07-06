"""
IID-CONTENT-INJECT, IID-LECTURE-CONTENT
Load all .qmd and .md files from the content/ folder, strip Quarto-specific
syntax, and concatenate into a single plain-text string for LLM injection.
"""

import re
import sys
from pathlib import Path


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block (--- ... ---)."""
    return re.sub(r"^---\n.*?\n---\n?", "", text, count=1, flags=re.DOTALL)


def _strip_quarto_syntax(text: str) -> str:
    """Remove Quarto/Pandoc-specific markup, keeping readable prose."""
    # Incremental reveal dots
    text = re.sub(r"^\. \. \.$", "", text, flags=re.MULTILINE)
    # Div fences with attributes:  ::: {.class} or :::callout-tip
    text = re.sub(r"^:::[^\n]*$", "", text, flags=re.MULTILINE)
    # Image tags: ![alt](path){attrs}
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)\{[^}]*\}", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Inline attribute spans: [text]{.class}
    text = re.sub(r"\[([^\]]+)\]\{[^}]*\}", r"\1", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_sections(files: list[Path]) -> list[str]:
    """IID-CONTENT-INJECT: Clean each file and wrap it in a `### [filename]` section."""
    sections: list[str] = []
    for f in files:
        raw = f.read_text(encoding="utf-8")
        cleaned = _strip_quarto_syntax(_strip_frontmatter(raw))
        if cleaned:
            sections.append(f"### [{f.name}]\n\n{cleaned}")
    return sections


def load_files(files: list[Path]) -> str:
    """IID-CONTENT-INJECT: Clean and concatenate an explicit list of content files.

    Used for `extra_content` entries in `_meta.yaml` (IID-MULTI-COURSE) — shared
    files injected into a course on top of its own folder. Raises SystemExit if
    a file is missing so a bad path fails loudly at startup.
    """
    for f in files:
        if not f.is_file():
            sys.exit(f"[Lectos] ERROR: extra content file '{f}' not found.")
    return "\n\n---\n\n".join(_clean_sections(files))


def load_content(content_dir: str | Path) -> str:
    """
    IID-CONTENT-INJECT: Read all .qmd and .md files, clean, and concatenate.
    Raises SystemExit if the folder is missing or yields no content.
    """
    content_path = Path(content_dir)
    if not content_path.is_dir():
        sys.exit(f"[Lectos] ERROR: content directory '{content_dir}' not found. "
                 "Create the folder and add at least one .qmd or .md file.")

    # IID-EDUCATOR-CONFIG: files prefixed with _ are app-config files, not lecture content
    files = [f for f in sorted(content_path.glob("**/*.qmd")) + sorted(content_path.glob("**/*.md"))
             if not f.name.startswith("_")]
    if not files:
        sys.exit(f"[Lectos] ERROR: content directory '{content_dir}' is empty. "
                 "Add at least one .qmd or .md file.")

    return "\n\n---\n\n".join(_clean_sections(files))
