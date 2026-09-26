---
name: weekly-report
description: Analyse one week of Lectos Timeseries student chats and write the weekly lecturer report (tool problems, worst AI answers, student flags, what students focused on and struggled with). Used unattended by scripts/weekly_report.py every Wednesday; can also be run by hand on a week folder under exports/timeseries/. IID-WEEKLY-REPORT.
---

# Weekly report on the Timeseries chats (IID-WEEKLY-REPORT)

You write the analysis part of a weekly e-mail to the lecturer of "Univariate Time Series
Analysis" (Basel). Students ask questions to Lectos, an AI tutor that answers from the
lecture material. The lecturer wants to know, in 5 minutes of reading, where the tool
failed and where the students are.

## Inputs (all in the week folder you were given, e.g. `exports/timeseries/week_2026-09-30/`)

- `stats.json` — counts, period, session index (S01, S02, … with name, e-mail, times)
- `transcripts.md` — every session, chronological. `### [hh:mm] STUDENT`, `TUTOR`,
  `⚑ FLAG Fn`, `ERROR` headings mark the turns. Sessions marked NON-STUDENT are the
  lecturer or tests: use them only for "tool problems", never for what students focus
  on or struggle with.
- `flags.md` — every student flag (F1, F2, …): the student's comment and the tutor
  message they flagged.
- The lecture material the tutor had: `content_timeseries/*.qmd` (`script_*` = lecture
  notes with definitions and derivations, the others = slide decks) and the tutor's
  instructions `content_timeseries/_system_prompt.md`.

Do not open `chats.html` (it is the same data as markup) and never read `.env` or
`credentials/`.

If no week folder was given, use the newest `exports/timeseries/week_*` folder.

## Method

1. Read `stats.json`, `flags.md`, `content_timeseries/_system_prompt.md`, then all of
   `transcripts.md` (in chunks if long).
2. For every tutor answer that looks doubtful, **check it against the lecture material**
   with Grep/Read before judging it: notation, definitions, conditions of theorems, signs,
   formulas. Standard time-series knowledge counts too, but say when the lecture differs
   from the textbook convention. Do not call an answer wrong without having checked.
3. Judge answers against the tutor's instructions as well: grounded in the lecture,
   concise, honest when something is not covered, cites "script"/"lecture slides",
   no invented page/section numbers, math rendered with `$…$`.
4. Evaluate each flag: was the student's complaint justified?

## What counts as a bad answer (rank by harm to learning)

1. Mathematically or substantively wrong (wrong formula, condition, sign, interpretation).
2. Contradicts the lecture's definitions/notation, or invents lecture content
   (claims "the slides say …" when they don't; guesses sections).
3. Doesn't answer the question asked, or the student had to ask again because the answer
   didn't land.
4. Misleading by omission (true but missing the key caveat), unrendered/broken math,
   far too long for the question, wrong language.

Report at most 5, fewer if fewer are bad. **If no answer is clearly bad, say so — do not
fill the list.**

## Output: `<week folder>/report_body.html`

Write one HTML **fragment** (no `<html>`, `<head>`, `<style>` or scripts — it is pasted
into an e-mail body, so use only inline `style=` attributes and simple tags: h3, p, ul,
li, b, i, blockquote, table, code). Plain math as text (e.g. `phi_1`, `|phi| < 1`), no
LaTeX. English. Refer to students by full name and to sessions by label, e.g.
"Anna Muster (S07, Tue 23 Sep)". Quote short verbatim excerpts (≤ 3 lines) in
`<blockquote style="border-left:3px solid #ccc;margin:6px 0;padding:2px 10px;color:#444">`.

The fragment must contain exactly these sections, in this order, each an `<h3>` with the
given `id` (the script checks the ids):

1. `<h3 id="summary">In short</h3>` — 3-5 bullets: the most important things the lecturer
   should know or do this week.
2. `<h3 id="tool-problems">Tool problems</h3>` — technical and behavioural problems of the
   tool: error messages/stalls (from `stats.json` errors and ERROR turns), rendering
   problems, instruction violations, unhelpful patterns that recur across sessions. Each
   with count/sessions affected. "None observed" if none.
3. `<h3 id="worst-answers">Worst AI answers</h3>` — ranked list. Per item: student + session
   + time; the question (short); excerpt of the answer; **what is wrong**; **what the
   material says** (file + section heading, e.g. `script_02-utsa-fundamentals.qmd`,
   "Stationarity"); severity (high/medium/low).
4. `<h3 id="flags">Student flags</h3>` — one entry per flag (F1, F2, …; all of them): one
   line on what the student complained about and your verdict — justified / partly /
   not justified — with a one-line reason. (The raw flags are appended to the mail
   automatically; do not repeat them in full.)
5. `<h3 id="focus">What students focused on</h3>` — topics ranked by how many students
   and sessions asked about them, mapped to lecture chapter/section. Short table
   (topic · chapter · students · sessions) plus 1-2 sentences on patterns (e.g. exam-style
   questions, exercise help, conceptual vs. computational).
6. `<h3 id="struggles">What students struggled with</h3>` — concepts where students
   showed misunderstanding, asked repeatedly, or followed up confused. Per item: the
   misconception in one sentence, who (names, sessions), a telling quote, and whether
   the tutor resolved it.
7. `<h3 id="suggestions">Suggestions</h3>` — concrete, few: what to clarify in the next
   lecture, what to change in the tutor prompt (`content_timeseries/_system_prompt.md`) or
   in the material. Only suggestions backed by something above.

Keep the whole fragment to what can be read in ~5 minutes. Be factual; no praise
padding. If the week had very few chats, say so and keep every section short.

Write the file with the Write tool as your final step, then reply with one line saying
it is written.
