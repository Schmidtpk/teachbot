# Handoff: fix learning-goals mode session churn (IID-LEARN-GOALS)

You are picking up an **open, unfixed bug**. A prior session diagnosed it thoroughly but did
not implement a fix (only reverted one unrelated aggravating factor — see "Already done"
below). Read this whole file before touching code; it contains the evidence trail so you don't
have to re-derive it.

## The complaint that started this

Student feedback (emine.oeztuerk@stud.uni-heidelberg.de, reported 2026-07-20): "the bot repeats
the intro questions." Investigation showed this is a symptom of **Chainlit sessions restarting
constantly** in learning-goals ("Practice") courses — each restart re-runs `on_chat_start`,
which in that mode automatically poses a fresh (re-worded) opening question.

## Already done (do not redo, but do build on it)

Commit `5160eed` (`fix(learn): revert deterministic goal-seed sampling`, plan
`goal_seed_rewind`, see `agent/done/goal_seed_rewind.md`) reverted a 2026-07-08 fix
(`5bbf345`) that made goal-sampling deterministic per student. That mechanism made restarts
re-serve the *same* goal every time (making the symptom read as "repeats itself" rather than
"keeps jumping to a new random goal"). Reverting it does **not** fix the churn — it only makes
churn read as goal-shuffling instead of question-repetition. **The actual root cause — why
sessions keep restarting — is still unfixed.** That is your job.

## What is confirmed (do not re-litigate; verified against real data)

Data source: `exports/sheets_backup_*.csv` (Google Sheets chat log, `IID-SHEETS-LOG`).
**Schema gotcha:** files from April–May 2026 use a 6-column schema
(`timestamp, session_id, user_email, role, content, flagged_message`) — no `course` column.
Files from June 2026 onward use 8 columns
(`timestamp, session_id, user_email, course, role, content, flagged_message, model`). Any
analysis across the full history MUST check the header row per file and skip/handle the old
schema separately, or `course`-based filtering silently misparses. To regenerate a fresh combined
export: `python scripts/archive_sheet.py` (this also **clears the live Sheet** — that's expected,
by design, per `IID-SHEETS-LOG`).

1. **The churn is exclusive to `mode: learning_goals` courses.** Across 9,254+ deduplicated rows
   and 1,339 sessions (8-column-schema files only), every single non-Practice course (Q&A,
   Exercise, prediction-market courses) has a **0% "opening-only session" rate**. All four
   Practice courses show heavy churn: Part III.1 (Monte Carlo) 81.3%, Part I 75.0%, Part III.3
   72.1%, Part II 60.0% (sessions where the *only* logged row is the auto-generated opening
   question — no student ever got to answer, or the session died before they could).
2. **Same-student, same-day, same-device comparison rules out device/network as sole cause.**
   Every student who used both a Practice course and a Q&A/Exercise course on the *same days*
   had **0% churn in the non-Practice course** and 30–100% churn in the Practice course
   (e.g. emine.oeztuerk: 0% in Q&A, 81.9% in Practice; joshua.trott: 0% in Exercise, 90.0% in
   Practice). This is the strongest evidence: it is not "some students have flaky phones," it's
   the app code exercised by learning-goals mode.
3. **Timeline:** churn existed from day one of learning-goals mode (2026-07-06, commit
   `361f676`), before the goal-seed commit (`5bbf345`, 07-08) existed — so the seed mechanism
   did not cause it, only changed its symptom (see above). Rate grew through July, spiking hard
   2026-07-17 to 07-19 (59% → 93.5% → 85.4% opening-only), coinciding with an exam-prep usage
   surge (few unique students, hundreds of sessions/day each).
4. **No application-level exceptions.** Railway deploy logs for the exact churn windows (checked
   via `railway logs --service teachbot --since <ISO> --until <ISO>`) show zero tracebacks/error
   lines — only routine `httpx` 200 OK completions and Chainlit translation-file warnings. The
   Python process is not crashing.
5. **Live corroborating evidence of a transport-level failure:** a spot-check of recent Railway
   HTTP edge logs (`railway logs --service teachbot --http --since <Nm>`) caught a real request:
   `GET /ws/socket.io/  0  10269ms` — a socket.io transport request that hung >10s and returned
   status `0` (aborted/no response). This is the same failure class as the churn, caught live.
6. **Timing match to Socket.IO's ping-timeout:** measured median gap between session restarts is
   **~21 seconds**. Chainlit does not override Socket.IO/engine.io's defaults — verified directly:
   `chainlit/server.py:230` constructs `socketio.AsyncServer(cors_allowed_origins=[],
   async_mode="asgi")` with no `ping_interval`/`ping_timeout` kwargs, and the installed
   `engineio.server.Server.__init__` defaults are `ping_interval=25`, `ping_timeout=20` (seconds).
   A ~20–21s restart cadence is consistent with the engine.io ping-timeout firing — i.e. the
   server or client misses a keep-alive cycle by ~20s, the transport is declared dead, and the
   client reconnects as a **brand-new Chainlit session** (no resume — `IID-SESSION-HISTORY` is
   not implemented), immediately re-running `on_chat_start`.

## Leading hypothesis (evidence-backed, not yet proven with a captured trace)

Learning-goals mode is structurally different from Q&A in exactly the way needed to explain
isolation to this mode:

- **Q&A's `on_chat_start` makes zero LLM calls.** It sends the welcome message and waits.
- **Learning-goals mode's `on_chat_start` always makes an LLM call immediately**
  (`_pose_goal_question`, `app.py` — search `IID-LEARN-GOALS` — calls `_stream_assistant`, which
  calls the LLM), before the student does anything. Every subsequent student turn then makes
  **two** sequential LLM calls (`_diagnostic_turn`: non-streamed JSON `diagnose_answer` +
  streamed `act`) versus Q&A's one streamed call per turn.

Hypothesis: latency/congestion in that automatic up-front call (or the non-streamed diagnose
call, which produces zero visible streaming activity while in flight) occasionally exceeds the
~20s ping-timeout window, especially under the concurrent load seen during the Jul 17-19
exam-prep surge. The reconnect this causes **itself fires another automatic LLM call**
(the new session's opening question), adding more load at exactly the moment congestion is
already high — a plausible self-reinforcing spiral that would explain why the rate *grew* rather
than staying flat. Q&A never exposes this window at all (no forced call at session start), so it
never spirals.

**This is not yet proven with a captured stack trace / timing log from the actual failure
moment** — Railway's historical HTTP-log retention would not let this session pull the exact
`2026-07-19T12:56–13:03Z` window (`--http --since <ISO> --until <ISO>` for a date >24h old
returned `Problem processing request`; only recent/relative windows like `--since 26h` worked,
and even those seem capped around ~500 lines / don't reliably reach back that far). Confirming
the precise stalling call requires the instrumentation below.

## Two code-level issues found during review — fix regardless of root-cause confirmation

1. **`src/llm_client.py`, `complete_json()` (~line 143): silently swallows every exception.**
   ```python
   except Exception:
       return {}
   ```
   No logging of what failed — network error, timeout, rate limit, connection reset all look
   identical to "model returned nothing." This is very likely why zero errors show up in the
   logs even though something is clearly going wrong. **Fix this first** — even just
   `print(f"[complete_json] {type(exc).__name__}: {exc}", file=sys.stderr)` before the `return {}`
   — and the next churn episode should immediately show what's actually failing (timeout?
   connection reset? something else?).

2. **`src/course_loader.py::build_system_prompt` + `app.py` (learning-goals branch of
   `on_chat_start`, search `cl.user_session.set("lecture_content", ...)`): `load_content()` runs
   TWICE per learning-goals session start** — once inside `build_system_prompt` (used by every
   mode) and again, redundantly, to populate the `lecture_content` cached for the diagnose call.
   It's synchronous file read + regex (`src/content_loader.py`), executed directly in the
   `async def on_chat_start` coroutine with no executor handoff — genuine blocking-the-event-loop
   time, done twice, only in this mode. Content sizes here are modest (20–50KB — actually smaller
   than several Q&A courses' content, e.g. `qna_part3` is 95KB vs `learn_part31`'s 19KB), so this
   alone is probably not sufficient to cause a 20s stall by itself, but it's free, avoidable
   blocking work concentrated in exactly the failing mode and should be de-duplicated (cache the
   result of one `load_content` call and reuse it) regardless of whether it's the primary cause.

## Recommended next steps (in order)

1. **Fix the silent exception swallow in `complete_json`** (above) — cheap, safe, immediately
   informative. Deploy it before anything else; it turns the next churn episode into a source of
   real evidence instead of silence.
2. **Add duration logging** around: `_pose_goal_question`'s call to `_stream_assistant` (the
   automatic session-start LLM call), and `diagnose_answer` (the non-streamed call). Log
   wall-clock duration for both, in learning-goals mode only, to `logger`/stderr.
3. **Add Socket.IO/engine.io disconnect visibility.** Chainlit doesn't surface engine.io's
   `disconnect` events with a reason by default; check whether hooking
   `sio.eio.on('disconnect', ...)` or enabling `engineio_logger=True`
   (`socketio.AsyncServer(..., engineio_logger=True, logger=True)` — check Chainlit's version for
   a supported way to pass this through `chainlit/server.py:230`, or monkey-patch at app.py
   import time) gives per-session disconnect reasons/timestamps you can correlate against the
   Sheets session-restart timestamps.
4. **De-duplicate the double `load_content()` call** (issue #2 above) — low-risk cleanup,
   do it while you're in this code regardless of what the logging reveals.
5. **Once a next churn episode is captured with the above logging live**, re-pull the Sheets
   export (`python scripts/archive_sheet.py`) and Railway logs for that exact window
   (`railway logs --service teachbot --since <ISO> --until <ISO>` — use a *recent* window, this
   session confirmed only recent/relative ranges reliably return data) and correlate: which call
   was in flight when a session died? Did the new duration logging show an outlier before the
   gap? Did the disconnect handler fire with a reason?
6. **Only after the precise stalling point is confirmed**, design the actual fix. Plausible
   candidate directions (not vetted, do not implement blind):
   - Move the automatic opening-question call so it streams into the UI incrementally the same
     way Q&A responses do (it already does via `_stream_assistant`/`stream_token` — confirm this
     is genuinely keeping traffic flowing to the client during the call, or whether something
     buffers it).
   - Investigate whether OpenRouter/the configured `diagnose_model` has elevated tail latency
     under concurrent load (check OpenRouter's activity/latency dashboard for the account, if
     accessible, for the Jul 17-19 window) — if so, consider a hard timeout + fallback on the
     diagnose call specifically (it already degrades gracefully to generic feedback on failure —
     `Diagnosis.from_raw({})` — so a timeout wrapped around `complete_json` may be a safe,
     surgical fix: fail fast to the existing fallback path instead of risking the ping-timeout).
   - Consider whether Chainlit/Socket.IO's ping/pong timing can be safely widened
     (`ping_timeout`/`ping_interval`) as a blunter mitigation, understood as papering over the
     symptom rather than fixing the underlying latency.
   - `IID-SESSION-HISTORY` (currently `CANDO`, unimplemented) — persisting/resuming a session
     across a transport drop would make any remaining reconnects invisible to the student instead
     of restarting the goal-drill from scratch. Bigger lift; consider only if the above doesn't
     fully resolve it.

## Key files / IIDs for this investigation

| File | Relevance |
|---|---|
| `app.py` | `_pose_goal_question` (auto LLM call at session start, learning-goals only), `_diagnostic_turn` (two-call turn), `on_chat_start` |
| `src/tutor_loop.py` | `diagnose_answer`, `complete_json` caller — the non-streamed call |
| `src/llm_client.py` | `complete_json` (silent exception swallow, line ~143), `stream_response` |
| `src/goals.py` | `sample_goal` (already simplified — do not reintroduce seeding without solving churn first) |
| `src/course_loader.py` | `build_system_prompt` — first (of two) `load_content()` calls per learning-goals session start |
| `src/content_loader.py` | `load_content` — the synchronous file-read + regex work |
| `.venv/Lib/site-packages/chainlit/server.py:230` | where the Socket.IO server is constructed (defaults confirmed here) |
| `exports/sheets_backup_*.csv` | raw data for re-running this analysis — **mind the 6- vs 8-column schema split** |
| `agent/done/goal_seed_rewind.md` | the prior (related but separate) fix already shipped |

**IIDs:** `IID-LEARN-GOALS`, `IID-LEARN-DIAGNOSE` (primary — this is where both extra LLM calls
live), `IID-SHEETS-LOG` (data source), `IID-SESSION-HISTORY` (CANDO, relevant long-term
mitigation), `IID-CHAT-SHELL1` (Chainlit shell/session lifecycle).

## Process reminder (per CLAUDE.md)

This file is a diagnosis handoff, not an approved plan. Before writing a fix: propose a plan
(mention the IIDs above), discuss/confirm the approach with the user — especially step 6's
candidate directions, which are genuinely unvetted — then implement, test, save the outcome to
`agent/done/<plan_name>.md`, and commit referencing `IID-LEARN-GOALS`/`IID-LEARN-DIAGNOSE` and
the plan name.
