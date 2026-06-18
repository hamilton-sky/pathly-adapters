# DESIGN_SPEC — Local AI Inference Service

Feature: `comms-board` (artifact summarization) + cross-reference `editor-notebook-enhancements`
Author: architect
Date: 2026-06-17
Question: Should both features share one centralized "local AI inference" service?

---

## TL;DR recommendation

**Build a small `runner/inference.py` module — a Python function, not an HTTP
endpoint — and have ONLY Feature 1 (artifact summarization) consume it.**

**Do NOT try to make Feature 2 (editor assistant) consume it.** The editor
assistant is renderer-only by deliberate design (`editor-notebook-enhancements/
DESIGN_SPEC.md` §"No IPC / no FSM / no Python changes", lines 604-608). It spawns
a CLI as a visible PTY via `window.pathly.terminal.spawn(...)` — that *is* its
inference call, and routing it through Python would be a regression, not a
consolidation. The two features look similar ("spawn an AI call") but sit on
**opposite sides of the process boundary** and have **opposite interaction
models** (fire-and-forget batch vs. interactive visible terminal).

The honest answer to "should we centralize?" is: **centralize the thing that is
actually shared, which is the backend-selection POLICY, not the call mechanism.**
That shared surface is one tiny config helper, not a service.

---

## 0. The finding that overturns the premise

```
Feature 1 — artifact summarization          Feature 2 — editor "Ask Agent/Explain"
──────────────────────────────────          ──────────────────────────────────────
Runs in:   Python (http_server/runner)       Runs in:   Electron renderer (React)
Trigger:   file dropped on board (server)     Trigger:   user selects text + clicks
Latency:   fire-and-forget, async OK          Latency:   interactive, wants streaming
Output:    short text → DB column             Output:    a live terminal the user reads
Mechanism: needs a NEW call path              Mechanism: window.pathly.terminal.spawn
                                                          (ALREADY EXISTS, argv built
                                                           in tooltipActions.ts)
Backends:  MiniLM / Ollama / Haiku-CLI         Backend:   CLI agent in a PTY (claude/codex/agy)
```

These do not share a runtime, a transport, or a result shape. The only genuinely
shared concept is **"which backend should a local AI call use?"** — and even that
is only partly shared (the editor always uses an interactive CLI; it has no use
for MiniLM or fire-and-forget Ollama).

A "service both consume" implies a common caller surface. There is none without
inventing one (e.g. forcing the renderer to POST to a new `/inference` endpoint),
which would mean **discarding the editor's existing, working, visible-terminal
path** for no gain. That is a layer/architecture regression dressed as DRY.

> Design principle applied: don't unify call sites that differ in *process,
> latency model, and output shape*. Unify the *policy* they happen to reference.

---

## 1. What to build — `runner/inference.py`

A pure Python module in the **runner layer**. It is a function library, not a
server, not a class with state.

**Location:** `src/pathly_orchestrator/runner/inference.py`

**Why runner/ and not a new HTTP endpoint:**
- The only caller is `blueprints/comms.py` (the `/comms/attach` and `/comms/post`
  handlers), which is in `http_server/` and may freely import `runner/` (layer
  rule: `http_server` may import all). No new route is needed — summarization is a
  side effect of an *existing* attach/post call, not a user-facing API.
- It sits next to `embeddings.py` and `comms_context.py`, which is exactly where
  the MiniLM backend already lives. Backend #1 (MiniLM) is literally
  `embeddings.embed()` — co-locating is correct.
- Adding `/inference` would invite the renderer to call it, which §0 says we must
  not do. Keeping it a Python function makes the "server-side only" boundary
  structural, not just documented.

```
http_server/blueprints/comms.py   (POST /comms/attach, /comms/post)
        │  lazy import (route handler), layer-legal
        ▼
runner/inference.py  ── summarize_artifact() ──┐
        │                                       │
        ├─► backend "minilm"  → embeddings.embed (no gen, returns None summary)
        ├─► backend "ollama"  → http POST 127.0.0.1:11434/api/generate
        └─► backend "haiku"   → resolve_argv() + subprocess (reuses invoke.py argv)
                                       │
        ▼                              ▼
runner/embeddings.py            runner/argv.py (resolve_argv)
db/queries/comms.py (update_artifact_summary, embed_async)
```

---

## 2. Interface

```python
# src/pathly_orchestrator/runner/inference.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SummaryResult:
    summary: str | None          # None when backend is embed-only (minilm) or failed
    backend: str                 # which backend actually ran ("minilm"|"ollama"|"haiku"|"none")
    cost_usd: float = 0.0        # >0 only for haiku CLI path
    error: str | None = None     # set on failure; caller logs, never raises to the route

def summarize_content(
    text: str,
    *,
    artifact_type: str = "md",   # "md"|"code"|"pdf"|"image"|"json" — tunes the prompt
    backend: str | None = None,  # None => resolve from settings (see §3)
    max_sentences: int = 3,
    timeout: int = 30,
) -> SummaryResult:
    """Generate a short summary of *text*. Never raises — failures return
    SummaryResult(summary=None, error=...). Synchronous; callers wanting
    fire-and-forget wrap it in summarize_async (see §4)."""

def summarize_async(
    artifact_id: str,
    message_id: str,
    text: str,
    *,
    artifact_type: str = "md",
    backend: str | None = None,
) -> None:
    """Fire-and-forget: run summarize_content in a daemon thread, then write the
    result to comms_artifacts.summary and post a context board message.
    Mirrors embeddings.embed_async exactly (same daemon-thread + best-effort DB
    write pattern). Returns immediately."""
```

**Design notes on the interface:**
- `text` in, `SummaryResult` out — no DB handles, no message objects. Pure.
- **Never raises.** It follows the established repo idiom (`embed()` returns
  `None` on failure; `comms_context` returns `""` on any exception). A dropped
  file must never 500 the attach route.
- `artifact_type` tunes the prompt (code gets "summarize what this code does";
  image is rejected/skipped for text backends — see scope guard §6). It does not
  branch backends.
- The **embed-only "MiniLM" backend is modeled as `summary=None`**. That is
  truthful: MiniLM cannot generate prose. Choosing it means "no summary, rely on
  raw-chunk embedding" — the caller then embeds raw truncated content via the
  existing `embed_async`, exactly today's behavior. So "MiniLM backend" =
  "summarization disabled", which is a legitimate, zero-infra default.

---

## 3. Backend selection — `app_settings` row, overridable per-call

Use the **existing `app_settings` table** (`db/queries/app_settings.py`) with a
**new global key**, resolved by a thin helper. Precedence:

```
explicit backend= param   >   app_settings row   >   env var   >   hard default
   (test / future UI)          (the real knob)        (ops)        ("minilm")
```

```python
# add to db/queries/app_settings.py
_INFERENCE_BACKEND_KEY = "inference:summary_backend"
_VALID_BACKENDS = {"minilm", "ollama", "haiku"}

def get_summary_backend(conn) -> str:
    raw = get_setting(conn, _INFERENCE_BACKEND_KEY)
    if raw in _VALID_BACKENDS:
        return raw
    env = os.environ.get("PATHLY_SUMMARY_BACKEND")
    if env in _VALID_BACKENDS:
        return env
    return "minilm"            # safe zero-infra default

def set_summary_backend(conn, backend: str) -> None:
    if backend not in _VALID_BACKENDS:
        raise ValueError(...)
    set_setting(conn, _INFERENCE_BACKEND_KEY, backend)
```

**Why a single global key, not per-feature:**
- There is exactly one consuming feature (artifact summarization). Per-feature
  config is speculative — YAGNI.
- It mirrors how `app_settings` already stores cross-cutting config
  (`board_scope:*`, `write_permissions:*`). The pattern is `get_X/set_X` helpers
  over a string key. We follow it verbatim.

**Why not an env var as the primary knob:** the user said "user-configurable."
A DB row can be flipped from Studio (a future settings toggle) at runtime; an env
var requires a server restart and isn't visible. Env var stays as an ops-level
override only.

---

## 3a. Upload path — per-upload backend + embed the summary

The two producers of artifacts are not symmetric. An **agent-created** artifact is
posted by a CLI with no human watching; an **uploaded** artifact is dropped by a
human in Studio, who *can* be asked one question. The backend selector (§3) already
draws this line — `backend=` is the highest-precedence override — so the upload path
just **surfaces that override as a UI picker** and the agent path leaves it `None`.
No new backend logic: the picker is a *producer* of the existing per-call override,
nothing more. This stays inside the §6 scope guard (three fixed backends, no plugin
registry).

```
producer            backend= passed to summarize_async      who decides
─────────────       ──────────────────────────────────      ───────────
agent-created       None  → resolve app_settings default     nobody (silent,
  (CLI posts)              (§3 precedence), fire-and-forget    fire-and-forget)
user-uploaded       picker value: "minilm" | "ollama"        the human, at
  (Studio drop)            | "haiku"  → forwarded verbatim     upload time
```

**The picker (uploads only).** Studio's upload/attach UI offers three choices that
map 1:1 onto the existing backends (§3 `_VALID_BACKENDS`):

| Picker label | `backend=` value | Effect |
|---|---|---|
| **Off** | `"minilm"` | embed-only; no prose summary (`summary=None`, §2) |
| **Local model** | `"ollama"` | offline generate via local Ollama (§1) |
| **Haiku** | `"haiku"` | spawn the Haiku CLI one-shot (§1, §7) |

The upload/attach endpoint accepts an **optional `backend` param** and forwards it
verbatim to `summarize_async(backend=…)`. It is validated against the same
`_VALID_BACKENDS` set §3 already enforces; an absent/invalid value falls through to
the §3 precedence chain (so a malformed picker value degrades to the app default, it
never errors the upload). **Agents are never prompted** — the agent-created post
path passes `backend=None` and silently resolves the `app_settings` default, exactly
as §4's fire-and-forget shape describes. The picker changes *who chooses*, not *what
the choices are*: it is the §3 per-call override with a face.

**Embed the generated summary for uploaded artifacts.** Today two channels are
separate: the artifact `summary` feeds the **catalog** (browse/read), and the
existing per-message MiniLM embedding (`embeddings.embed_async`, one row per message,
`chunk_index=0`) runs over the **message text** (search). For an uploaded file the
message text is a thin "uploaded `X`" note — so in semantic search the file is
findable only by its filename. **On the upload path specifically, when a summary is
generated, use that summary as the text the existing per-message embedder sees** — so
one generated summary serves BOTH the catalog (browse) and semantic search (find).
Recommend this as the **default for uploads**.

```
upload path (summary generated):
  summarize_async(..., backend=<picker>)
        │  summary = "<generated ≤3-sentence summary>"
        ├─► update_artifact_summary(...)        → catalog description (browse)
        └─► embed_async(message_id, text=summary)  → per-message vector (search)
              (the SAME embedder, just fed the summary instead of the "uploaded X" note)
```

**This is artifact-level, on the existing per-message channel — NOT section-level
embedding.** It does not revive the section-/summary-level vector index rejected in
`DESIGN_SPEC-context-retrieval.md §8`. The only thing that changes is *what text the
one already-existing per-message embedder is handed* for an uploaded artifact: its
generated summary instead of a near-empty upload note. No new embedding rows per
section, no per-artifact summary-vector table, no new model — `store_embedding`'s
`chunk_index=0` per-message model is untouched. If the backend is **Off** (`minilm`,
`summary=None`) there is no generated summary to embed, so the embedder falls back to
the message text exactly as today. The context-retrieval spec records the matching
scoped exception in its §5a.3, so the two specs agree: for **agent-created** artifacts
and in general, summary ≠ embedding source; for **uploaded** artifacts on this path,
the summary does double duty (catalog + search) via the existing per-message channel.

---

## 4. Async model

Two distinct shapes, both already have precedent in the repo:

```
Feature 1 (this service): FIRE-AND-FORGET
  /comms/attach handler ──► insert_artifact() (gets a row + id, summary=NULL)
                       ──► summarize_async(artifact_id, message_id, text)   ← returns instantly
                                  │ daemon thread (copy of embeddings.embed_async)
                                  ▼
                          summarize_content(...)  (blocks in the thread, not the request)
                                  │
                                  ├─► update_artifact_summary(conn, artifact_id, summary)
                                  └─► post_message(type="context", text=summary)  ← agents can now find it
                                          └─► embed_async(...) on that context msg (existing pipeline)

Feature 2 (editor): STREAMING / INTERACTIVE — NOT this service
  tooltip ──► window.pathly.terminal.spawn(tabId, cwd, undefined, argv)
              (visible PTY, user watches it stream; supervisor terminal pattern)
```

The attach route stays synchronous and fast — it returns `{ok, message_id}` the
instant the artifact row exists. The summary lands a few seconds later via a
second `COMMS_UPDATE` SSE broadcast (`event: "artifact_summarized"`) so the board
card updates live. This is the **same two-phase pattern embeddings already use**
(post returns immediately, embedding fills in async). No new infrastructure.

> The interactive/streaming requirement in the question belongs **entirely** to
> Feature 2, and Feature 2 already satisfies it with the PTY path. This service
> therefore only needs the fire-and-forget shape. Do not build streaming into it.

---

## 5. Where each call site hooks in

| Call site | File:area | Change |
|---|---|---|
| Artifact attach | `blueprints/comms.py` `comms_attach()` ~line 608 | After the `insert_artifact(...)` call, add `summarize_async(artifact_id, message_id, row["text"]_or_filecontent, artifact_type=artifact_type)`. Note: `insert_artifact` returns the id — capture it (today its return is discarded). |
| Artifact post | `blueprints/comms.py` `comms_post()` ~line 199 | Same hook after the `type=="artifact"` `insert_artifact(...)`. |
| Summary writeback | `db/queries/comms.py` | **NEW** `update_artifact_summary(conn, artifact_id, summary, token_count=None)` — single `UPDATE comms_artifacts SET summary=?, token_count=? WHERE id=?`. Today `summary` is only ever set at insert from `row["text"]`; this lets the async job replace it with a real generated summary. |
| Backend config | `db/queries/app_settings.py` | **NEW** `get_summary_backend` / `set_summary_backend` (§3). |
| The content itself | inference.py | For `md/code/json` read the file at `artifact_path` (truncate to N chars). **`image`/`pdf` are out of scope** — see §6. |

**Important correctness note:** `insert_artifact` is idempotent per
`(message_id, path)` and currently seeds `summary` with the *message text*. The
async job must `UPDATE` by `artifact_id` (returned from insert), not re-insert.
That is why `summarize_async` takes `artifact_id`, not just `message_id`.

---

## 6. What NOT to build (scope guard)

1. **Do NOT add an `/inference` HTTP endpoint.** It would tempt the renderer to
   call it and break the editor's deliberate renderer-only design (§0). Keep it a
   Python function reachable only from `http_server` route handlers.

2. **Do NOT route the editor assistant (Feature 2) through this.** It is
   renderer-only by design. Leave `tooltipActions.ts` + `terminal.spawn` exactly
   as the editor spec describes. This service has zero overlap with it at the
   code level.

3. **Do NOT build content extraction for `image` and `pdf` now.** MiniLM and a
   text-prompt LLM can't read an image; PDF text extraction is a separate
   dependency (pypdf/pdfminer) with its own failure modes. For v1: `image` →
   summary stays the filename/alt-text; `pdf` → skip or summarize first-page text
   only if a deps already present, else skip. Flag as a follow-up. The
   `_EXT_ARTIFACT_TYPE` map already buckets these; the service just early-returns
   `SummaryResult(summary=None, backend="none")` for them.

4. **Do NOT build streaming / token-by-token output.** Only Feature 2 wants it,
   and Feature 2 gets it from the PTY. Fire-and-forget is the only shape here.

5. **Do NOT make a backend abstraction with plugins/registry.** Three backends,
   one `if/elif/else` in `summarize_content`. A registry/ABC is over-engineering
   for N=3 with no third-party extension story.

6. **Do NOT auto-start Ollama or bundle it.** If backend=`ollama` and the local
   server isn't reachable, return `error="ollama unreachable"` and fall back to
   `minilm` (summary=None). Never block the attach. Document the
   `ollama serve` + `ollama pull` prerequisite; don't manage the process.

7. **Do NOT add a new model-pricing path for the Haiku backend cost.** Reuse
   `parse_result` from `runner/output.py` (it already extracts `cost_usd`). The
   `SummaryResult.cost_usd` is informational; billing telemetry for these tiny
   calls is out of scope for v1.

---

## 7. Layer-violation check (against `src/pathly_orchestrator/CLAUDE.md`)

```
db/         ──  no imports up.   NEW update_artifact_summary lives here. OK.
runner/     ──  may import db.   inference.py imports db.queries.comms +
                                 db.queries.app_settings + runner.embeddings +
                                 runner.argv. All same-or-lower layer. OK.
supervisor/ ──  not involved. (Good — summarization is not a pipeline stage.)
http_server/──  may import all.  comms.py route lazily imports runner.inference
                                 inside the handler (matches existing lazy-import
                                 idiom at every other comms route). OK.
```

The Haiku-CLI backend uses `resolve_argv` + `subprocess.Popen` directly from
`runner/inference.py` rather than calling `runner/invoke.py:invoke_agent` —
because `invoke_agent` is built for pipeline-stage semantics (state/topic prompt
prefix, abort callbacks, AGENT_DONE patching). A summary call wants none of that.
Reusing only `resolve_argv` keeps it in-layer and avoids dragging stage machinery
into a one-shot text call.

```
inference.summarize_content (backend=haiku):
   argv = resolve_argv("claude", prompt, "claude-haiku-4-5-...", interactive=False)
          → appends --print --output-format=json automatically (argv.py:62)
   out  = subprocess.run(argv, capture_output=True, timeout=...)
   res  = parse_result("claude", out.stdout)   # reuse output.py
   return SummaryResult(summary=res["result"], backend="haiku", cost_usd=res["cost_usd"])
```

---

## 8. Recommended default + rollout

- Ship with `backend="minilm"` (zero new infra, zero new deps, today's behavior
  but now structurally a "summarization disabled" choice).
- Make `haiku` the recommended on-switch: it reuses the entire existing CLI
  invocation stack and needs no local model download. One DB row flips it on.
- Treat `ollama` as the "fully offline / no API cost" option for users who've
  already set it up — supported, not defaulted, never auto-managed.

```
Effort estimate (relative):
  inference.py (3 backends, if/elif)      ~120 lines
  update_artifact_summary + settings      ~25 lines
  two route hooks + 1 SSE event           ~15 lines
  ───────────────────────────────────────────────
  No new endpoint, no new table, no renderer change, no supervisor change.
```

---

## Open question for the human

The MiniLM "backend" doesn't summarize — it just means "embed raw chunks, no
prose summary." Two ways to model the default:

- **(A)** Default `minilm` = summarization OFF; `comms_artifacts.summary` stays
  the message text (today's behavior); agents semantically search raw content.
  Zero behavior change until a user opts into haiku/ollama. *(My recommendation —
  safest, no new runtime dependency on day one.)*
- **(B)** Default `haiku` = summaries generated out of the box; every dropped file
  costs a fraction of a cent and needs the Anthropic CLI authenticated.

I recommend (A): it makes the new capability strictly opt-in and keeps the
zero-dependency promise, while (B) silently introduces a per-drop API cost and an
auth precondition that could fail on a fresh install.
