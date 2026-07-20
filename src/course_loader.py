"""
IID-MULTI-COURSE, IID-EDUCATOR-CONFIG
Discover and configure course contexts from content/ subfolders.

Each non-`_`-prefixed subfolder of the root content directory is a course.
A `_meta.yaml` file (required) in each subfolder supplies at minimum `lecture_name`.
Missing `_meta.yaml` or missing `lecture_name` → loud startup failure.

Fallback chain (see IID-MULTI-COURSE):
  _system_prompt.md : subfolder → root content dir
  _welcome.md       : subfolder → root content dir
  model / temperature / max_tokens / diagnose_model : _meta.yaml → config.yaml llm section
  lecture_name / {{course_name}}   : _meta.yaml → config.yaml course_name
  student_model_choices (IID-STUDENT-MODEL-CHOICE) : subfolder _meta.yaml → root content/_meta.yaml

Optional `extra_content` in _meta.yaml: list of file paths relative to the content
root (e.g. `_shared/script0.qmd`) injected before the course's own folder content —
lets several courses share one file without duplication.
"""

import sys
import yaml
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from src.content_loader import load_content, load_files


@dataclass
class CourseConfig:
    """IID-MULTI-COURSE: Fully-resolved configuration for one course context."""
    course_id: str           # subfolder name
    lecture_name: str        # display name; substituted for {{course_name}}
    description: str         # markdown description shown in profile chooser
    order: int               # sort order from _meta.yaml (default 999)
    content_dir: Path        # absolute path to the course subfolder
    system_prompt_path: Path # resolved: subfolder/_system_prompt.md or root fallback
    welcome_path: Path       # resolved: subfolder/_welcome.md or root fallback
    llm: dict                # merged LLM config: _meta.yaml overrides → config.yaml defaults
    diagnose_prompt_path: Path | None = None  # IID-LEARN-DIAGNOSE: resolved _diagnose_prompt.md (goals mode)
    first_date: date | None = None  # IID-MULTI-COURSE: inclusive lower bound of availability
    last_date:  date | None = None  # IID-MULTI-COURSE: inclusive upper bound of availability
    student_model_choices: list[dict] = field(default_factory=list)  # IID-STUDENT-MODEL-CHOICE: [{id, label}, ...]
    mode: str = "qa"  # IID-LEARN-GOALS: "qa" (default) or "learning_goals"
    learning_goals: list[dict] = field(default_factory=list)  # IID-LEARN-GOALS: [{id, title, goal, material?}, ...]
    extra_content: list[Path] = field(default_factory=list)  # IID-MULTI-COURSE: shared files injected before folder content

    def is_available(self, today: date) -> bool:
        """IID-MULTI-COURSE: True iff today falls inside the (optional) availability window."""
        if self.first_date and today < self.first_date:
            return False
        if self.last_date and today > self.last_date:
            return False
        return True

    def availability_line(self) -> str:
        """IID-MULTI-COURSE: Markdown line describing the window; "" when no bounds set."""
        if self.first_date and self.last_date:
            return f"_Available: {self.first_date.isoformat()} – {self.last_date.isoformat()}_"
        if self.first_date:
            return f"_Available from {self.first_date.isoformat()}_"
        if self.last_date:
            return f"_Available until {self.last_date.isoformat()}_"
        return ""


def _parse_meta_date(value: Any, folder_name: str, field: str) -> date | None:
    """IID-MULTI-COURSE: Coerce _meta.yaml date field to datetime.date or None.

    PyYAML auto-parses bare YYYY-MM-DD into date; accept ISO strings too for forward compat.
    Loud SystemExit on malformed input naming the folder and field.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            sys.exit(
                f"[Lectos] ERROR: '_meta.yaml' in '{folder_name}' has invalid '{field}' "
                f"value '{value}'. Expected ISO date YYYY-MM-DD."
            )
    sys.exit(
        f"[Lectos] ERROR: '_meta.yaml' in '{folder_name}' field '{field}' must be a "
        f"YYYY-MM-DD date (got {type(value).__name__})."
    )


def _load_learning_goals(folder: Path, mode: str) -> list[dict]:
    """IID-LEARN-GOALS: Load and validate `_learning_goals.yaml` for a learning-goals course.

    Returns [] for non-learning_goals courses. For mode == "learning_goals", the file is
    required and must hold a non-empty `goals` list of dicts, each with a unique non-empty `id`.
    A goal may carry an optional `material` string — code/formulas/data the student must see,
    displayed verbatim by the app itself (see src/goals.py) — which must be a string if present.
    Fails loudly (SystemExit) naming the folder, matching discover_courses' fail-loud style.
    """
    if mode != "learning_goals":
        return []

    goals_path = folder / "_learning_goals.yaml"
    if not goals_path.exists():
        sys.exit(
            f"[Lectos] ERROR: course '{folder.name}' has mode 'learning_goals' but no "
            f"_learning_goals.yaml. Add it with a non-empty 'goals:' list."
        )
    try:
        with goals_path.open(encoding="utf-8") as fh:
            data: dict = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        sys.exit(f"[Lectos] ERROR: failed to parse '{goals_path}': {exc}")

    goals = data.get("goals")
    if not isinstance(goals, list) or not goals:
        sys.exit(
            f"[Lectos] ERROR: '_learning_goals.yaml' in '{folder.name}' must contain a "
            f"non-empty 'goals' list."
        )

    seen: set[str] = set()
    for g in goals:
        if not isinstance(g, dict) or not str(g.get("id", "")).strip() or not str(g.get("goal", "")).strip():
            sys.exit(
                f"[Lectos] ERROR: every goal in '{folder.name}/_learning_goals.yaml' needs a "
                f"non-empty 'id' and 'goal'."
            )
        gid = str(g["id"])
        if gid in seen:
            sys.exit(
                f"[Lectos] ERROR: duplicate goal id '{gid}' in "
                f"'{folder.name}/_learning_goals.yaml'."
            )
        seen.add(gid)
        if g.get("material") is not None and not isinstance(g["material"], str):
            sys.exit(
                f"[Lectos] ERROR: goal '{gid}' in '{folder.name}/_learning_goals.yaml' has a "
                f"'material' field that is not a string."
            )

    return goals


def discover_courses(root: Path, base_cfg: dict[str, Any]) -> list[CourseConfig]:
    """IID-MULTI-COURSE: Scan root for course subfolders; return sorted list of CourseConfig.

    Returns [] when no non-`_` subfolders exist (caller uses single-course fallback).
    Fails loudly (SystemExit) if a subfolder is missing _meta.yaml or lecture_name.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        sys.exit(f"[Lectos] ERROR: content directory '{root}' not found.")

    subfolders = sorted(
        p for p in root.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )
    if not subfolders:
        return []

    base_llm = dict(base_cfg.get("llm", {}))

    # IID-STUDENT-MODEL-CHOICE: load global model choices from root content/_meta.yaml
    global_model_choices: list[dict] = []
    root_meta_path = root / "_meta.yaml"
    if root_meta_path.exists():
        try:
            with root_meta_path.open(encoding="utf-8") as fh:
                root_meta: dict = yaml.safe_load(fh) or {}
            global_model_choices = [
                {"id": m["id"], "label": m.get("label", m["id"])}
                for m in root_meta.get("student_model_choices", [])
                if isinstance(m, dict) and "id" in m
            ]
        except yaml.YAMLError:
            pass  # optional file — malformed YAML silently produces no global choices
    courses: list[CourseConfig] = []

    for folder in subfolders:
        meta_path = folder / "_meta.yaml"

        # IID-MULTI-COURSE: _meta.yaml is required — fail loudly if absent
        if not meta_path.exists():
            sys.exit(
                f"[Lectos] ERROR: course subfolder '{folder.name}' has no _meta.yaml. "
                f"Add a _meta.yaml with at least 'lecture_name', or remove the subfolder "
                f"from content/ if it is not a course."
            )

        try:
            with meta_path.open(encoding="utf-8") as fh:
                meta: dict = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            sys.exit(f"[Lectos] ERROR: failed to parse '{meta_path}': {exc}")

        if not meta.get("lecture_name"):
            sys.exit(
                f"[Lectos] ERROR: '_meta.yaml' in '{folder.name}' is missing required "
                f"field 'lecture_name'."
            )

        # Resolve fallback paths for app-config markdown files
        def _resolve(filename: str) -> Path:
            local = folder / filename
            return local if local.exists() else root / filename

        # Merge LLM config: base_cfg["llm"] as defaults, _meta.yaml keys as overrides
        # (diagnose_model: IID-LEARN-DIAGNOSE / IID-COST-CACHE — cheap model for the diagnose call)
        llm_overrides = {
            k: meta[k]
            for k in ("model", "temperature", "max_tokens", "diagnose_model")
            if k in meta
        }
        merged_llm = {**base_llm, **llm_overrides}

        # IID-MULTI-COURSE: optional availability window
        first_date = _parse_meta_date(meta.get("first_date"), folder.name, "first_date")
        last_date  = _parse_meta_date(meta.get("last_date"),  folder.name, "last_date")
        if first_date and last_date and first_date > last_date:
            sys.exit(
                f"[Lectos] ERROR: '_meta.yaml' in '{folder.name}' has first_date "
                f"({first_date.isoformat()}) after last_date ({last_date.isoformat()})."
            )

        # IID-STUDENT-MODEL-CHOICE: per-course list; falls back to root content/_meta.yaml
        raw_choices = meta.get("student_model_choices", [])
        if raw_choices:
            student_model_choices = [
                {"id": m["id"], "label": m.get("label", m["id"])}
                for m in raw_choices
                if isinstance(m, dict) and "id" in m
            ]
        else:
            student_model_choices = global_model_choices

        # IID-LEARN-GOALS: behavioral mode + learning goals
        mode = str(meta.get("mode", "qa"))
        learning_goals = _load_learning_goals(folder, mode)

        # IID-MULTI-COURSE: optional extra_content — shared files (paths relative to
        # the content root) injected into this course in addition to its own folder
        raw_extra = meta.get("extra_content", [])
        if raw_extra and not isinstance(raw_extra, list):
            sys.exit(
                f"[Lectos] ERROR: '_meta.yaml' in '{folder.name}' field 'extra_content' "
                f"must be a list of paths relative to '{root}'."
            )
        extra_content: list[Path] = []
        for entry in raw_extra:
            p = root / str(entry)
            if not p.is_file():
                sys.exit(
                    f"[Lectos] ERROR: '_meta.yaml' in '{folder.name}' lists extra_content "
                    f"'{entry}', but '{p}' does not exist."
                )
            extra_content.append(p)

        courses.append(CourseConfig(
            course_id=folder.name,
            lecture_name=meta["lecture_name"],
            description=meta.get("description", ""),
            order=int(meta.get("order", 999)),
            content_dir=folder,
            system_prompt_path=_resolve("_system_prompt.md"),
            welcome_path=_resolve("_welcome.md"),
            llm=merged_llm,
            diagnose_prompt_path=_resolve("_diagnose_prompt.md"),  # IID-LEARN-DIAGNOSE
            first_date=first_date,
            last_date=last_date,
            student_model_choices=student_model_choices,
            mode=mode,
            learning_goals=learning_goals,
            extra_content=extra_content,
        ))

    # Sort by order field (from _meta.yaml) then lecture_name for deterministic profile ordering
    courses.sort(key=lambda c: (c.order, c.lecture_name))
    return courses


def load_course_text(path: Path, course_name: str) -> str:
    """IID-MULTI-COURSE, IID-EDUCATOR-CONFIG: Read a markdown config file, substituting {{course_name}}.

    Returns "" if the file does not exist. Supersedes _load_app_text in app.py.
    """
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    return text.replace("{{course_name}}", course_name)


def load_course_content(course: CourseConfig) -> str:
    """IID-CONTENT-INJECT, IID-MULTI-COURSE: course folder content, with `extra_content` merged in.

    Extracted out of `build_system_prompt` so a caller that needs the raw content for more
    than one purpose (learning-goals mode caches it separately for the diagnose call — see
    IID-LEARN-DIAGNOSE, `agent/session_churn_fix_handoff.md`) can load and clean the files
    once and reuse the string, instead of re-reading and re-cleaning them per use.
    """
    content = load_content(course.content_dir)
    # IID-MULTI-COURSE: extra_content files (e.g. shared intro/syllabus) come first
    if course.extra_content:
        content = f"{load_files(course.extra_content)}\n\n---\n\n{content}"
    return content


def build_system_prompt(course: CourseConfig, content: str | None = None) -> str:
    """IID-QNA-CORE, IID-CONTENT-INJECT, IID-EDUCATOR-CONFIG, IID-MULTI-COURSE:
    Assemble the full system prompt for a course: instructions + injected lecture content.

    Accepts optional pre-loaded `content` (from `load_course_content`) so a caller that
    already has it doesn't trigger a redundant file read; defaults to loading it fresh.
    """
    instructions = load_course_text(course.system_prompt_path, course.lecture_name)
    if content is None:
        content = load_course_content(course)
    return (
        f"{instructions}\n\n"
        f"--- LECTURE CONTENT START ---\n{content}\n--- LECTURE CONTENT END ---\n"
    )
