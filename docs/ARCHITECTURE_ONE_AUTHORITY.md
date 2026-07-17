# One Authority — Collapsing Pathly's Parallel Mechanisms

> **Status: design north-star / proposal.** This describes a direction, not the current
> state. Where it names current code, that code is the *starting* point to collapse, not a
> finished implementation. Do not "sync" this doc to the code — it is a target the code
> should move toward.

## The through-line

Four subsystems in Pathly each grew a second (or third) parallel mechanism answering the
same question. Every place two mechanisms answer one question is a place they can **drift** —
and every compensating "net" we've added exists only because there were two. The
highest-leverage architectural work is not new features; it is collapsing each of these to
**one authority, with everything else a labeled projection of it.**

| Subsystem | The one authority | Everything else becomes… |
|---|---|---|
| **Prompts** | `compose` (skill + fragments + abilities) | presets/abilities = overrides; the composed prompt = a persisted artifact |
| **Telemetry** | one result endpoint → one parser → one projection → one pricing chokepoint | client parsers = live-display only |
| **Context** | one `assemble_context(scope, task) → ContextBlock` | retrieval = a READ over the board; consolidation = a WRITE over the board |
| **State** | SQLite (runtime truth) | disk files = SEED (input) **xor** EXPORT (output), never round-tripped for truth |

The test to apply everywhere: **"is this a new layer, or a new query/write over an existing
layer?"** Almost always it's the latter — and modeling it as a subsystem is what created the
drift.

---

## Issue #1 — Prompts: compose is the one registry

### The issue
A prompt sent to a CLI is assembled from several sources — the agent persona, the skill body,
the un-editable Pathly **fragments** (board CRUD, progress logging, completion-report /
`AGENT_DONE`), and the new layer-3 **abilities**. Historically the assembly logic and the
"library" of reusable prompt text lived in more than one place (host built-ins vs. DB rows;
skill markdown vs. ad-hoc overrides), so "what exactly did this agent receive" was assembled
differently depending on the entry point (interactive `/pathly` vs. Studio runner vs. editor
one-shot).

### The destination
**`compose` is the single registry.** One composer turns `(agent, skill, abilities, caps)`
into a labeled, segmented prompt; presets and abilities are *overrides/addenda* layered onto
that composition, never a parallel source. Concretely, this is the direction already being
built:

- `skills/compose.py::compose_skill_segments()` returns **labeled segments**;
  `segments_to_prompt()` joins them byte-identical to `compose_skill()`. `extra_segments=` is
  where abilities append.
- `db/queries/prompt_library.py` is the **one store** behind every prompt dropdown
  (`kind='preset'` single-select) — host built-ins **merge** with the user's rows
  (`useMergedPresets`), so there is no "built-ins vs. library" duality at the point of use.
- **Abilities are FILES** (`pathly/abilities/<cat>/<name>.md`, `~/.pathly/abilities/…`),
  read at compose time exactly like fragments — one authority, no DB/file duality.
- The pre-spawn **gate** shows the composed prompt and its layers (`headingLayers`), and a
  Sections trim now sends the **complete** composed prompt as a `prompt_override` (the server
  uses only that — it does not re-assemble around it).

### What remains
1. **Persist the composed prompt per run.** The exact text sent should be an artifact keyed
   by `run_id`, so telemetry/audit can answer "what did this agent see" without re-deriving
   it. This pairs directly with Issue #2 (one result path) and #3 (one context block) — both
   halves of the final prompt then come from one composer each.
2. **Persist the gate's SELECTION, not trimmed text, for reusable pre-config** (flow phase
   inspector). Store `{ability_ids, excluded_sections}` per stage (via `stage_configs`), and
   **compose fresh at spawn + apply the selection**. Storing trimmed *text* would freeze a
   stale-seed snapshot — the same bug class as Issue #4.

---

## Issue #2 — Telemetry: one spawn chokepoint

### The issue
There are **two** telemetry ingestion paths, and every compensating net exists because there
are two:

- **`/runner/terminal/result`** — supervised runs. Event-projected:
  `AGENT_DONE` → invocation projection (`db/queries/invocation_projection.py`) → superseding
  `BILLING_UPDATE` folded in → `_price_if_needed`.
- **`/db/invocation`** — editor one-shots. Direct write, `source_seq NULL`, **bypasses** the
  event projector and its pricing chokepoint — which is why we needed the parallel codex
  parser in Studio (`codexJson.ts::parseCodexResult`), the estimate in
  `runner/telemetry.py::project_agent_done`, and the server re-parse bolted onto
  `db_api_invocation.py`.

Two parsers, two pricing sites, two places "what did this run cost" can diverge. The whole
`$0`-for-codex / truncated-envelope / vanished-run saga lives in the seam between them.

### The destination
Make a one-shot a **degenerate supervised run**, so there is literally one path:

> PTY exits → **one** result endpoint → **one** parser (`runner/output.py::parse_result`) →
> (real or synthetic) `AGENT_DONE` → **one** projection → **one** pricing chokepoint.

### Migration (each step independently shippable)
1. **Give every editor one-shot a lightweight run identity.** It already spawns through the
   same gate (`terminal.ts`); the only difference is it posts to `/db/invocation`. Register
   it as a runner tab (topic `editor:diagram:<file>`, a synthetic `run_id`) so its PTY-exit
   posts to `/runner/terminal/result` like everything else.
2. **Generalize the synthetic-`AGENT_DONE` net (Fix A) to the one-shot case.** The only thing
   that made one-shots "special" was "no supervisor, no `AGENT_DONE`" — but we already solved
   "no `AGENT_DONE`" by synthesizing one (`supervisor/terminal.py::_synthesize_agent_done_if_missing`).
   Make the result handler synthesize from parsed stdout for **any** run that didn't emit one.
   Now the one-shot flows through the identical projection + pricing.
3. **Delete the second path.** `/db/invocation` goes away; `parseClaudeJsonResult` /
   `parseCodexResult` in the gate keep only their **live-terminal-display** role (not
   telemetry); `project_agent_done`'s parallel estimate and the `db_api_invocation` re-parse
   both evaporate.

The synthetic-`AGENT_DONE` net stops being a "net" and becomes the **normalization step**:
one place turns "a process exited with some stdout" into a canonical `AGENT_DONE`, whether or
not the agent self-reported. That is the collapse.

---

## Issue #3 — Context: one `assemble_context`

### The issue
Three mechanisms all answer one question — *"what context does this agent get?"* — but each is
a separate subsystem with its own storage/endpoints/logic:

- **(a) the board itself** — `retrieve_board_context` / `runner/comms_context.py`, injected
  into prompts.
- **(b) context-retrieval** — per-task `context_refs` manifest → `/comms/artifacts/<id>/section`
  hydration (`runner/hydrate.py`) → Board Catalog → client-side AI-Router summaries.
- **(c) memory-consolidation** — relevance-gated context channel, near-dup dedup, a manual
  reflection pass via `/comms/consolidate`.

A blackboard has **one** store and the control shell decides what each knowledge source reads.
Pathly has the store plus two more layers on top — and each layer is a place where "what the
agent saw" can diverge from "what's on the board." Same drift-risk family as the telemetry
saga, and it makes "what exactly did this agent see" hard to answer because it's assembled
from three sources.

### The destination
Reframe (b) and (c) as a **query** and a **write-pattern** over (a), not subsystems. Apply the
test ("new layer or new query?"):

- **Context-retrieval is a READ over the board.** "Select the relevant artifacts/decisions for
  this task, hydrate the referenced sections." Keep `context_refs` as **metadata on the task**
  (which board items are relevant); the retrieval itself is just SELECT + hydrate. Not a
  substrate.
- **Memory-consolidation is a WRITE over the board.** Dedup near-identical artifacts; the
  consolidated summary is **just another board artifact** with a type (`summary` /
  `consolidated`) — a higher-level item the same read surfaces. Not a separate memory.
- **Unify behind one entry point:** a single `assemble_context(scope, task) → ContextBlock`
  that (1) queries the board for relevant items, (2) treats consolidation output as
  just-another-artifact-type it already surfaces, and (3) returns the exact text injected. That
  function becomes **the** answer to "what did the agent see," identical everywhere — and it
  pairs with #1's "persist the composed prompt," because then both halves (skill+fragments and
  context) come from one composer each.

### Honest caveat
There may be a real reason (b)/(c) were split — latency (the AI-Router summary is client-side),
or a materialized context cache. So the pragmatic version isn't "merge all the code tonight";
it's **establish the one entry point and the one store now**, route the existing layers through
`assemble_context` and into the board (consolidation writes back as typed artifacts), and let
any cache be an internal detail *behind* that function. From the outside: one context
operation, one store.

---

## Issue #4 — State: DB is truth; disk is seed-in xor export-out

### The issue
The duality — `STATE.json` + `BOARD.json` + `EVENTS.jsonl` on disk + SQLite + `~/.pathly` —
isn't wrong, but the rule ("DB authoritative, disk mirror") is stated **loosely**, and the
stale-seed bugs live in the loose seams (e.g. the flow-YAML "append-not-replace" upsert that
made a team run dead-end at a human gate because YAML edits never reached runtime).

### The destination
Tighten it to a hard, one-directional rule **per data kind**. Every piece of state has exactly
**one** authority. Classify every file as SEED, EXPORT, or DB — never two at once, never
round-tripped for truth.

1. **Runtime truth = SQLite, always.** No runtime decision ever reads a disk file that also
   has a DB copy. (Flow YAML already had exactly this bug — the fix was "DB-first, YAML is a
   seed." Generalize it to all mirrors: `BOARD.json` is never read to *drive* behavior.)
2. **Disk files are SEED (input) xor EXPORT (output):**
   - **Seeds** (flow YAML, templates): read **once** at import/onboard → written to DB with
     **replace** semantics (the append-not-replace bug was the stale-seed root cause) → never
     read again at runtime. A seed edit requires an explicit, logged re-import; the UI should
     say *"this YAML is a seed — edits apply on re-import,"* so nobody expects live edits to
     take effect.
   - **Exports** (`BOARD.json` git mirror, `EVENTS.jsonl`): written **from** the DB for
     git-tracking / audit / human-diff. **Never read back to decide anything.** One-directional
     projection — the same shape as the invocation projection we already trust.
3. **Global vs. project = a scope filter, not a second truth.** One DB, `project_root`-normalized
   scope (the direction G2 already set). `~/.pathly` global is a `WHERE`, not another authority.

### Make it enforceable, not just documented
A CI check that greps for **runtime reads of mirror files** (any `BOARD.json` read outside the
export writer) **fails the build** — exactly like the dash-safety mirror tests. The rule that
kills the whole bug class, in one line for the root `CLAUDE.md`:

> **If it's in the DB, the disk copy is a write-only projection. If it's a seed, it's read once
> into the DB and then inert. Nothing reads a mirror to make a decision.**

---

## The synthesis

Every one of these is the same move — collapse two-or-three parallel mechanisms into **one
chokepoint** with the others as **explicit derived views**:

- **Prompts** — compose is the one registry; presets/abilities are overrides; the composed
  prompt is a persisted artifact.
- **Telemetry** — one result endpoint; client parsers are display-only.
- **Context** — one `assemble_context`; retrieval/consolidation are its read/write.
- **State** — DB is truth; disk is seed-in or export-out.

That single discipline — **one authority, everything else a labeled projection** — is what
turns Pathly from "many seams that drift" into "boring to operate." It is the
highest-leverage work on the board right now.
