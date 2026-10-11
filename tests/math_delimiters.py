"""
IID-UI-RENDER
Offline tests for `src/math_delimiters.py`: `\\(…\\)` / `\\[…\\]` in model answers become the
`$…$` / `$$…$$` the chat renders — also when a delimiter is split across stream chunks —
while code and LaTeX line breaks stay untouched.

Run:  .venv\\Scripts\\python tests/math_delimiters.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.math_delimiters import MathDelimiterStream, normalize_math  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


def streamed(text: str, cuts: list[int]) -> str:
    conv = MathDelimiterStream()
    parts, prev = [], 0
    for c in sorted(cuts) + [len(text)]:
        parts.append(conv.feed(text[prev:c]))
        prev = c
    return "".join(parts) + conv.flush()


CASES = [
    # (label, model output, what the student must see)
    ("display \\[ \\] → $$ (the reported case)",
     "So\n\\[\ny_t=\\frac{\\theta(B)}{\\phi(B)}e_t.\n\\]\nHence",
     "So\n$$\ny_t=\\frac{\\theta(B)}{\\phi(B)}e_t.\n$$\nHence"),
    ("inline \\( \\) → $",
     "the root \\(|z| > 1\\) of \\(\\phi(z)\\)",
     "the root $|z| > 1$ of $\\phi(z)$"),
    ("dollar math untouched",
     "already $x_t$ and $$\\sum_j \\psi_j$$ fine",
     "already $x_t$ and $$\\sum_j \\psi_j$$ fine"),
    ("\\\\ line break (\\\\[4pt]) untouched",
     "$$\\begin{aligned} a &= b \\\\[4pt] c &= d \\end{aligned}$$",
     "$$\\begin{aligned} a &= b \\\\[4pt] c &= d \\end{aligned}$$"),
    ("fenced code untouched",
     "```r\ngsub(\"\\\\(\", \"\", x)  # \\( stays\n```\nthen \\(x\\)",
     "```r\ngsub(\"\\\\(\", \"\", x)  # \\( stays\n```\nthen $x$"),
    ("inline code untouched",
     "use `grepl(\"\\(\", s)` for \\(s\\)",
     "use `grepl(\"\\(\", s)` for $s$"),
    ("other escapes untouched",
     "a \\* b and \\_ and \\frac{1}{2}",
     "a \\* b and \\_ and \\frac{1}{2}"),
    ("trailing backslash kept",
     "ends with \\",
     "ends with \\"),
]


def main() -> None:
    print("case: whole text")
    for label, raw, want in CASES:
        got = normalize_math(raw)
        check(got == want, f"{label}" + ("" if got == want else f" (got {got!r})"))

    print("\ncase: streamed in pieces (every split point, and random splits)")
    rng = random.Random(0)
    for label, raw, want in CASES:
        ok = all(streamed(raw, [k]) == want for k in range(len(raw) + 1))
        ok = ok and streamed(raw, list(range(1, len(raw)))) == want  # one char per chunk
        ok = ok and all(streamed(raw, rng.sample(range(len(raw) + 1), min(4, len(raw) + 1))) == want
                        for _ in range(50))
        check(ok, f"{label}: same result however the stream is cut")

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
