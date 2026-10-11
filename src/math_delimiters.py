"""
IID-UI-RENDER
LaTeX delimiters in the model's answers, converted to the forms the chat renders.

Chainlit renders math only between `$…$` (inline) and `$$…$$` (display). Models often write
`\\(…\\)` and `\\[…\\]` instead, whatever the prompt says; markdown then eats the backslash
and the student sees `[ y_t = \\frac{\\theta(B)}{\\phi(B)} e_t ]` as raw text.

`MathDelimiterStream` rewrites those delimiters while the answer streams, so the student
never sees the broken form: `\\(`/`\\)` → `$`, `\\[`/`\\]` → `$$`. A delimiter split across
two chunks is still caught (a trailing backslash is held back until the next chunk).
Untouched: code (``` fences and `inline code`, where `\\(` can be a regex), and `\\\\`
(a LaTeX line break, as in `\\\\[4pt]`).
"""

_REPLACE = {"(": "$", ")": "$", "[": "$$", "]": "$$"}


class MathDelimiterStream:
    """IID-UI-RENDER: feed() streamed text in, get display-ready text out; flush() at the end."""

    def __init__(self) -> None:
        self._pending = ""      # held-back tail: a lone backslash or a run of backticks
        self._fence = False     # inside a ``` code block
        self._inline = False    # inside `inline code`

    def feed(self, chunk: str) -> str:
        text = self._pending + chunk
        self._pending = ""
        out: list[str] = []
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == "`":
                j = i
                while j < n and text[j] == "`":
                    j += 1
                if j == n:  # the run may continue in the next chunk
                    self._pending = text[i:]
                    break
                run = j - i
                if run >= 3:
                    self._fence = not self._fence
                elif not self._fence:
                    self._inline = not self._inline
                out.append(text[i:j])
                i = j
                continue
            if ch == "\\" and not self._fence and not self._inline:
                if i + 1 == n:  # `\` + `[` may arrive in two chunks
                    self._pending = "\\"
                    break
                nxt = text[i + 1]
                if nxt == "\\":  # LaTeX line break `\\`, keep both
                    out.append("\\\\")
                    i += 2
                    continue
                if nxt in _REPLACE:
                    out.append(_REPLACE[nxt])
                    i += 2
                    continue
            out.append(ch)
            i += 1
        return "".join(out)

    def flush(self) -> str:
        """End of the answer: whatever was held back, as it was."""
        tail, self._pending = self._pending, ""
        return tail


def normalize_math(text: str) -> str:
    """IID-UI-RENDER: the same conversion for a complete text."""
    conv = MathDelimiterStream()
    return conv.feed(text) + conv.flush()
