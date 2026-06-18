# DESIGN_SPEC — Comms-Board Context-Retrieval Architecture

Feature: `comms-board` (context retrieval for DAG tasks)
Author: architect
Date: 2026-06-18
Cross-references:
- [DESIGN_SPEC-local-inference.md](DESIGN_SPEC-local-inference.md) — the offline
  summarizer (`runner/inference.py`) that populates `comms_artifacts.summary`, which
  feeds the INDEX tier here (the Board Catalog description + the `/section` summary field;
  it is **not** an embedding source — see §8). **That spec owns the summarizer; this spec
  consumes it.**
- [GOALS-DAG-EXECUTORS.md](GOALS-DAG-EXECUTORS.md) · [DAG-SCHEDULER-ARCHITECTURE.md](DAG-SCHEDULER-ARCHITECTURE.md)
  · [phases/PHASE-0b-planner-dag-wiring.md](phases/PHASE-0b-planner-dag-wiring.md) ·
  [phases/PHASE-1-dispatcher.md](phases/PHASE-1-dispatcher.md) · [ROADMAP.md](ROADMAP.md)

Question this spec answers: **In the DAG model, how does a task-executor (and its later
reviewer) reliably reach the advisory plan artifacts — `EDGE_CASES.md §Phase-3`,
`HAPPY_FLOW.md`, `ARCHITECTURE_PROPOSAL.md` — that the old file-reading builder hit by
walking the whole scope?**

---

## TL;DR recommendation

The gap is a **broken link, not a search problem**. In the file-reading model the builder
opened the scope and reached `EDGE_CASES §Phase-3` by cross-reference. In the DAG model a
task's `text` carries only `Purpose/Files/Done-when/Depends-on`
(`plan.md:324-337`), the advisory artifacts are posted but marked "not linked to tasks",
and the linkage silently vanishes. Embeddings do not fix this — a reviewer of Phase 3
needs *the Phase-3 section of EDGE_CASES*, deterministically, not a fuzzy match.

Build a **context manifest + two-tier retrieval**:

1. **`context_refs`** — a new JSON column on `comms_messages`. Each entry is
   `{artifact, anchor}` (e.g. `{"artifact": "EDGE_CASES.md", "anchor": "phase-3"}`). The
   planner fills it when emitting the task (`plan.md` Step 6). The executor AND its later
   reviewer hydrate **the same refs** — the link is now data, carried on the task row.
2. **Section anchoring by heading convention.** `## Phase 3` → slug `phase-3`. A
   **section index** (anchor → line-range + per-section summary) is built at
   artifact-write time and stored in a new **`comms_artifact_sections`** table. An
   optional `<!-- pathly:anchor id="..." -->` escape hatch covers sections that don't
   map to a heading.
3. **`GET /comms/artifacts/<id>/section?anchor=…`** — the HYDRATE endpoint. Returns the
   exact section's **full text** (line-range slice of the file), with explicit
   stale-index detection (mtime + content hash).
4. **Three query modes, in priority order** wired into `comms_context.py`: STRUCTURED
   (deterministic SQL) → HYDRATE (manifest section fetch) → SEMANTIC (the **existing
   per-message** embedding, discovery-only, verify-before-acting — v1 adds no new vectors).
5. **A Board Catalog** for taskless agents (§5a): an agent with **no `context_refs`** orients
   via a deterministic `{path, type, title, summary}` listing over the board's artifacts —
   a table of contents, not the documents — then hydrates its picks through the same
   `/section` endpoint. This is the **third access pattern**, alongside the task-driven
   manifest and query-driven semantic. The manifest and catalog yield section/artifact
   pointers that resolve at `/section`; the existing per-message semantic channel yields
   message-level pointers for discovery (the agent then browses and hydrates). All three
   terminate at the one hydration endpoint (§1.1). The catalog is plain deterministic SQL —
   part of the v1 spine, and v1 is the whole plan: there is no deferred semantic phase
   behind it (§8).

```
                       THE BROKEN LINK (today)
  planner ── writes ──► EDGE_CASES.md  HAPPY_FLOW.md  ARCH_PROPOSAL.md
     │                       (advisory — NOT linked to any task)
     │
     └─ posts task ──► task.text = {Purpose, Files, Done-when, Depends-on}
                              │
                              ▼
                     executor / reviewer  ──✗──►  EDGE_CASES §Phase-3
                       (no structured path to find it)

                       THE FIX (this spec)
  planner ── writes ──► EDGE_CASES.md  (## Phase 3 heading)
     │                       │  write-time index
     │                       ▼
     │              comms_artifact_sections: (phase-3 → L40-78 + summary)
     │
     └─ posts task ──► task.context_refs = [{EDGE_CASES.md, phase-3}, ...]
                              │
              ┌───────────────┴────────────────┐
              ▼                                 ▼
        executor                          reviewer (same refs)
              │   GET /comms/artifacts/<id>/section?anchor=phase-3
              ▼
        full text of EDGE_CASES §Phase-3  ◄── lossless HYDRATE
```

---

## 0. Codebase findings that constrain the design

Every claim below is verified against source on `shammai/cli-controls` (2026-06-18).

| # | Finding | Location | Constraint it imposes |
|---|---|---|---|
| F1 | `task.text` is the **self-contained** builder prompt: `Phase N / Purpose / Files: / Done when:` + a "read FEATURE_INDEX, stay in scope" footer. No advisory-artifact references. | `plan.md:311-337` | The manifest must be carried **out-of-band** from `text`; we cannot rely on the executor parsing prose for artifact links. |
| F2 | The `single` executor reads ONLY `text` + `artifact_path` ("open it for context"). The advisory files are never opened. | `drain-dag.md:37-39` | HYDRATE must be an explicit step the executor/reviewer performs from `context_refs`; there is no implicit scope walk. |
| F3 | Each task already carries `artifact_path` (single value) + `artifact_type`, populated by the planner (`IMPLEMENTATION_PLAN.md` / `plan_artifact`). | `plan.md:357-358`; `comms.py:188-189` | `artifact_path` is the *primary* spec; `context_refs` is the *secondary advisory* set. Keep them separate — don't overload `artifact_path` into a list. |
| F4 | `comms_messages` columns include `goal_id`, `executor`, `depends_on` (JSON array), `lane`, `task_status`, `claimed_by`, `artifact_path`, `artifact_type`. | `migrations.py:218-245`, `:367-379` | STRUCTURED mode already has every deterministic filter it needs — `goal_id`, `depends_on`, `task_status`, `lane`, `stage`. No new query columns required for STRUCTURED. |
| F5 | Additive migrations are an idempotent `ALTER TABLE ... ADD COLUMN` list; re-runnable (`try/except OperationalError`). The list ends at `executor` (line 379). | `migrations.py:342-385` | `context_refs` is **one more tuple appended to this list** — zero-risk additive migration, exactly how `goal_id`/`executor` landed. |
| F6 | `comms_artifacts` already has idle `summary`, `token_count`, `version`, `supersedes`, `last_edit_at`, `last_edit_by`. Artifact **content is NOT in the DB** — `path` is a filesystem reference; readers open the file. | `migrations.py:251-265`; ROADMAP "deferred polish" | `summary` is the INDEX-tier slot (filled by the inference service). Section text is fetched by **reading the file at `path`**, not from the DB. The endpoint is a file slicer, not a DB blob reader. |
| F7 | `insert_artifact` is idempotent per `(message_id, path)`; `version` defaults to 1; `last_edit_*`/`supersedes` stay NULL (hooks deferred). A `comms_artifacts` row is created **only for `type="artifact"` messages**, NOT for `type="task"`. | `comms.py:311-346`; `comms.py:197-209`; `comms.py:608-620`; PHASE-0b:104 | A plan artifact only gets a row if something posts it as a `type="artifact"` message. **This is exactly what §10 Q3=(b) resolves to do** — the planner posts each advisory file in Step 6 (§6 row 7), so new plans get rows + eager indexes for free. The section-index build must therefore still be able to locate a row **by `(scope, path)`** (the by-path hydrate, §4.1) and create a minimal one for *legacy* plans that predate this — hence the defensive `find_or_create_artifact_by_path` (§6 row 2d). |
| F8 | `embeddings.py` = `all-MiniLM-L6-v2`, 384-dim, **per-message, chunk_index=0, no chunking**. `store_embedding` writes one row per message into `comms_embeddings` (vec0 virtual table). | `embeddings.py:44-58`; `comms.py:411-429`; `migrations.py:271-283` | **SEMANTIC = this existing per-message embedding, kept as-is**, scoped to exposed boards (§8). It returns **message-level** pointers, not section anchors. Embedding *summaries* into their own per-artifact/per-section rows — and any per-section chunking — would reuse this same `store_embedding` shape but is **explicitly rejected, not deferred** (§8). Do not touch the `chunk_index=0` model. |
| F9 | `retrieve_board_context` returns a two-channel block: `### 🔒 Governance (always applies)` (deterministic: pending decisions + active escalations) and `### 💡 Context (verify before acting)` (semantic/recency hits). Governance is computed first and excluded from the semantic pool. Returns `""` on any failure. | `comms_context.py:144-276` | The three query modes map cleanly: STRUCTURED ⊇ today's Governance; SEMANTIC = today's Context channel; HYDRATE is a **new third channel** between them. The "never break the prompt — return ''" idiom is mandatory for the new code too. |
| F10 | The comms blueprint uses a strict idiom: lazy imports inside each handler, `request.get_json()` validation, `jsonify({"error":...}), <code>`, and `_broadcast_comms(scope, {...})` for SSE. Artifact routes: `GET /comms/artifacts?message_id=`, `POST /comms/attach`. | `comms.py:77-226`, `:637-658` | The new `/section` route must follow this idiom exactly (lazy import, validate, structured error codes, no SSE needed for a read). |
| F11 | Layer rule: `db < runner < supervisor < http_server`; renderer cannot import Python. Editor "Ask Agent" is renderer-PTY only (per editor spec + DESIGN_SPEC-local-inference §0). | `pathly_orchestrator/CLAUDE.md`; inference spec §0 | This is a **Python-side design only**. Section parsing lives in `runner/` (importable by `http_server` + `supervisor`); the DB write helpers live in `db/`. No renderer changes; do NOT reroute the editor. |
| F12 | No `context_refs`, no `anchor`, no `section_index`, no `comms_artifact_sections`, no `pathly:anchor` parsing exists anywhere in `src/`. | grep (verified) | Greenfield. No existing convention to honor or migrate; we define it. |

**The finding that frames the whole spec (F1 + F2 + F7):** the link from a phase task to
`EDGE_CASES §Phase-3` was never lossy — it was *absent*. The fix is to make the planner
*write the link* (`context_refs`) and give consumers a deterministic way to *follow it*
(anchors + section endpoint). Embeddings are the fallback for links the planner didn't
draw, not the primary mechanism.

---

## 1.0 How it works end-to-end (the lifecycle in three acts)

The whole design reduces to one shape: a `.md` artifact is **stored once, read many ways,
and re-derived only when it structurally changes.** This is the orientation; the mechanics
live in the sections it cross-links — it does not restate them.

```
  ┌── STORE (once) ──────────────────────────────────────────────────────────┐
  │  agent-made or uploaded .md  ──►  board CARD (instant)                     │
  │                              ──►  async:  topic-map summary                │
  │                                           + section index (anchors)        │
  │                                           + per-message embedding          │
  └───────────────────────────────────────────────────────────────────────────┘
                                   │
  ┌── READ (many ways) ───────────▼──────────────────────────────────────────┐
  │  manifest / catalog / semantic  ──►  a section pointer                     │
  │                                 ──►  ONE /section hydrate  ──►  full text  │
  └───────────────────────────────────────────────────────────────────────────┘
                                   │
  ┌── CHANGE (only on structural edit) ─▼─────────────────────────────────────┐
  │  indexed_hash re-derives only what changed                                 │
  │  detail edit inside a section  ──►  summary + embedding STILL VALID         │
  │  add / remove / rename a heading ──►  re-summarize + re-embed               │
  └───────────────────────────────────────────────────────────────────────────┘
```

- **STORE (once).** A `.md` artifact — agent-authored (planner Step 6, §6 row 7) or
  user-uploaded — becomes a board **card** instantly, then is enriched **asynchronously**
  with its INDEX-tier topic-map summary, its **section index** of heading anchors, and the
  existing per-message embedding. *How the tiers split:* **§1**. *Eager vs. lazy index
  build:* **§3.3**.
- **READ (many ways).** Three access patterns — the task **manifest** (`context_refs`),
  the **catalog** (taskless browse), and **semantic** discovery — all yield a *pointer*,
  and every pointer terminates at the **one** `/section` hydration endpoint that returns the
  full chapter text. *The three patterns side by side:* **§5 / §5a**. *Why a pointer-then-
  fetch split makes fuzzy retrieval safe:* **§1.1**.
- **CHANGE (only on structural edit).** The `indexed_hash` fingerprint re-derives **only
  what structurally changed.** A detail edit *inside* a section leaves the topic-map summary
  and the embedding valid — **no churn**; only adding, removing, or renaming a **heading**
  triggers a re-summarize + re-embed. *Staleness detection and rebuild:* **§3.4** (and the
  topic-map rationale in DESIGN_SPEC-local-inference §2a).

(`.md` only — the section/anchor/hydration model is heading-based; non-`.md` artifacts get
a card but no chapters. The hard boundary is §8 item 0.)

---

## 1. Two-tier retrieval (the core model)

```
  ════════════════════════ INDEX TIER (lossy — findability only) ═══════════
   per artifact:    comms_artifacts.summary        (≤3 sentences, generated)   [v1]
   per section:     comms_artifact_sections.summary (≤1 sentence per heading)  [v1]
   discovery:       per-MESSAGE 384-dim embedding (existing, F8)               [v1]
        │
        │  "this artifact / section is ABOUT X"  → used to FIND, never consumed as spec
        ▼
  ════════════════════════ HYDRATE TIER (lossless — what the agent consumes) ═
   GET /comms/artifacts/<id>/section?anchor=phase-3
        → exact line-range slice of the file at comms_artifacts.path
        → FULL section text. This is the payload the agent reads.
```

The **summaries** (artifact- and section-level) are a v1 deliverable — they feed the Board
Catalog (§5a) and the `/section` HYDRATE response, and exist as data the moment the
inference service fills them. The plan's **only vector channel is the existing per-message
embedding** (F8, §8); *embedding* these summaries into their own per-artifact/per-section
vectors is **rejected, not deferred** — see the scope guard (§8) for why and for the
cheaper keyword-first path to revisit if board-scale discovery ever proves insufficient.

**The invariant (locked decision 1):** a summary is a **pointer, never the payload**. An
agent decides *whether* a section is relevant from the INDEX tier, then HYDRATES to get
the real text. The skill prompts (§6) must state this explicitly so agents never paste a
summary into their reasoning as if it were the spec.

Why two tiers and not "just embed everything":
- Summaries are cheap to embed and cheap to inject into a prompt (the board context block
  is already token-budgeted, `comms_context.py:118-124` caps k=3/2/1). Full sections are
  not — injecting every advisory artifact in full would blow the prompt.
- Lossy is *correct* for findability and *wrong* for execution. Separating the tiers lets
  each be optimized for its job.

### 1.1 The unified pointer model (why fuzzy retrieval is safe here)

Every way of *finding* something on the board — whether the planner foresaw it or not —
produces a **pointer, never content**, and every pointer resolves to its bytes through a
**deterministic fetch** (§4). The two deterministic finders (the manifest and the catalog)
yield **section/artifact pointers** — `{artifact, anchor}` that the `/section` endpoint
slices directly. The one fuzzy finder (the existing per-message embedding) yields a
**message-level pointer** — it names the message/artifact that is *about* the query, and the
agent then browses the catalog or hydrates the artifact's sections from there. There is
always exactly one path from "this is relevant" to "here is the text," and it does not vary
by how the pointer was obtained:

```
  HOW the pointer was obtained                    WHAT it produces
  ─────────────────────────────────────────       ────────────────
  manifest  (context_refs — authoritative,     ──┐
            what the planner foresaw)            ├──►  a section/artifact
  catalog   (browse the board's summaries)     ──┘     pointer {artifact, anchor}
            (§5a — taskless orientation)                      │
                                                              │
  semantic  (similarity over per-message        ─────►  a message-level pointer
            embeddings — discovery, F8)              (→ browse catalog / hydrate)
                                                              │
                                                              ▼
                            GET /comms/artifacts/<id>/section?anchor=…
                                     (deterministic, lossless)
                                                              │
                                                              ▼
                                      FULL section text — the payload
```

**The safety property (the reason fuzzy retrieval is acceptable here):** semantic and catalog
**return pointers only; they never return content.** The deterministic `/section` fetch (or a
plain file read) is what delivers the bytes the agent consumes. So a *wrong* similarity hit
— a pointer to a message or artifact that turns out to be irrelevant — costs the agent exactly
**one discarded read.** It is never fed wrong content *as if it were truth*, because the fuzzy
step only ever names *where to look*; the authoritative step always slices the real file. This
is the structural reason a probabilistic finder is safe sitting in front of a deterministic
fetcher: imprecision in *where to look* is recoverable; imprecision in *what the spec says*
is not, and the hydration tier never introduces the latter.

The same property is why the three access patterns can coexist without ranking trust
between them: they differ only in *how confident the pointer is*, never in *how the content
arrives*. A manifest pointer is authoritative and a semantic pointer is a guess — but both
are validated the instant the agent reads the hydrated `text`, not before.

---

## 2. The context manifest

### 2.1 Shape

`context_refs` is a JSON array of objects, stored as a TEXT column on `comms_messages`:

```jsonc
// comms_messages.context_refs  (TEXT, JSON-encoded; NULL ⇒ no manifest ⇒ legacy behavior)
[
  { "artifact": "EDGE_CASES.md",          "anchor": "phase-3" },
  { "artifact": "HAPPY_FLOW.md",           "anchor": "phase-3" },
  { "artifact": "ARCHITECTURE_PROPOSAL.md","anchor": "data-layer" }
]
```

- `artifact` — the **basename** of a plan file in `pathly/plans/$FEATURE/`. Basename, not
  full path: it is resolved against the feature's plan folder at hydrate time (the same
  folder `artifact_path` already points into, F3). This keeps refs short and
  location-independent (matches the planner's `artifact_path` convention).
- `anchor` — a heading slug (§3.1) or an explicit `pathly:anchor` id. **Optional**: an
  entry with `anchor` omitted/`null` means "the whole artifact" (hydrate returns the full
  file; useful for short artifacts like a one-section `ARCHITECTURE_PROPOSAL`).

Each entry is intentionally minimal — `{artifact, anchor}`. No line numbers (they go
stale; Team-Safe rule in `plan.md:256` forbids the planner emitting line numbers anyway),
no summary (that lives in the section index), no embedding (INDEX tier owns that).

**`context_refs` are DERIVED, not hand-authored by the planner LLM (locked).** The entries
are produced **deterministically from the plan's own phase structure**, not written
free-hand by the model. The derivation: parse `IMPLEMENTATION_PLAN.md` for its `## Phase N`
headings (`plan.md:162-165`) and, for each phase task, emit
`[{EDGE_CASES.md, phase-N}, {HAPPY_FLOW.md, phase-N}]` (plus the optional
`ARCHITECTURE_PROPOSAL` section/whole-file ref per §10 Q1) — a mechanical
`phase N → §phase-N` mapping, the same one §3.1 step 2 already makes load-bearing. The LLM's
**only** job here is the easy half it is already good at: writing the advisory docs with
**consistent `## Phase N` headings** (the templates in §6 row 10 already enforce this). The
*linkage* itself — which task references which section — is a parse of structure the planner
already wrote, never a fresh authoring judgement.

> Why this matters: it takes the LLM **off the critical dependency of the authoritative
> path.** The 📎 channel (§5) is the *authoritative* spec an executor consumes; making its
> refs a deterministic derivation (rather than a thing the model might forget, mistype, or
> hallucinate) means the authoritative path depends on a parse, not on model diligence. The
> model only has to keep its headings consistent — a far smaller, template-enforced surface
> than authoring N correct `{artifact, anchor}` tuples by hand. This is the §8 item 7
> position ("the planner authors `context_refs` explicitly … the planner *does* the
> phase→anchor mapping") sharpened: the planner *owns* the mapping, but performs it by
> derivation from structure, not by free-hand authoring.

### 2.2 Storage decision — **new column on `comms_messages`** (RECOMMENDED, per locked decision 2)

| Option | Verdict |
|---|---|
| **A. New `context_refs` TEXT column on `comms_messages`** ✅ | Mirrors exactly how `depends_on` (a JSON array, `migrations.py:367`) and `goal_id`/`executor` were added. Queryable, indexable, survives independently of `text`, and is read with one row fetch the executor already does. Additive, zero-risk migration. |
| B. Embed inside `task.text` payload | Rejected. `text` is the human-and-agent-readable prompt; stuffing JSON into it pollutes the prompt, forces every consumer to parse prose (F1), and couldn't be queried (e.g. "which tasks reference EDGE_CASES?"). It also fights `update_message_text` (`comms.py:702`), which rewrites `text` on a goal rename and would clobber an embedded manifest. |

**Why a column, restated against the evidence:** `depends_on` set the precedent — a
structured DAG edge is a JSON column, not text the agent parses. `context_refs` is the
same kind of thing: a structured *advisory* edge. It belongs beside `depends_on`.

### 2.3 Migration

Append one tuple to the additive-migration list (`migrations.py:380`, after the
`executor` entry):

```python
# migrations.py — _add_additive_migrations(), append after the executor line
# comms-board context-retrieval: advisory artifact links carried on the task.
("comms_messages",      "context_refs",          "TEXT"),
```

Re-runnable (the `try/except sqlite3.OperationalError` skips existing columns,
`migrations.py:381-385`). No data backfill: a NULL `context_refs` is the legacy
fall-through (§7).

### 2.4 Write path — `post_message` + `/comms/post`

`post_message` (`comms.py:18-73`) gains one keyword param, JSON-encoded like `depends_on`:

```python
def post_message(
    conn, board, scope, from_agent, to_agent="*", type="nudge", text="",
    options=None, reply_to=None, stage=None, conv=None,
    depends_on=None, artifact_path=None, artifact_type=None,
    goal_id=None, executor=None,
    context_refs: list[dict] | None = None,   # NEW — advisory artifact manifest
) -> str:
    ...
    # INSERT column list gains  context_refs ; placeholder gains one ? ;
    # values tuple gains  json.dumps(context_refs) if context_refs is not None else None
```

`/comms/post` (`comms.py:77-226`) gains a read + a type guard mirroring `depends_on`
(`comms.py:164-168`):

```python
context_refs = data.get("context_refs")
if context_refs is not None and (
    not isinstance(context_refs, list)
    or not all(
        isinstance(r, dict) and isinstance(r.get("artifact"), str)
        and (r.get("anchor") is None or isinstance(r.get("anchor"), str))
        for r in context_refs
    )
):
    return jsonify({"error": "Field 'context_refs' must be a list of "
                             "{artifact:str, anchor?:str} objects or null"}), 400
# ... pass context_refs=context_refs into _post_message(...)
# ... add 'context_refs' to the route docstring "Optional:" line
```

**Validate-at-write — each ref must resolve to a real section, or fall back loudly.** The
shape check above proves an entry is *well-formed*; it does not prove the `anchor` actually
exists in the artifact. So at post time, after the shape guard and **after** the advisory
files have been posted + indexed (Step 6 posts the artifacts before the tasks, §6 row 7), the
write path **resolves each `{artifact, anchor}`** against the freshly-built section index
(`get_section(conn, artifact_id, anchor)` via the same `(scope, path)` lookup `/section`
uses, §4.1):

- **Resolves** → keep the ref verbatim.
- **Does not resolve** (anchor absent — a heading the planner expected isn't there, or was
  named differently) → **rewrite that entry to whole-file (`anchor: null`)** so the executor
  still gets the *whole* artifact rather than a dead pointer, **and emit a visible warning** —
  a board nudge (`post_message(type="nudge", …)`) naming the task + the unresolved
  `artifact §anchor`, plus a logged `logging.warning`. **Never silently drop the ref and never
  silently keep a dead anchor.** Whole-file fallback degrades a precise hydrate to a broader
  one (the §10 Q1 whole-file behavior, already a supported mode) instead of to *nothing*.

```
post task with context_refs:
  for each {artifact, anchor}:
     resolve via get_section(scope, artifact, anchor)
        ├─ found     → keep {artifact, anchor}
        └─ not found → rewrite to {artifact, anchor: null}     (whole-file fallback)
                       + board nudge  "⚠ task <id>: EDGE_CASES.md §phase-9 unresolved
                                        → hydrating whole file"
                       + logging.warning(...)
```

This composes with the read-side guards: even if a ref slips through unresolved (e.g. the
file is edited *after* the task is posted and a heading is later renamed), the `/section`
endpoint still returns `404 {anchor_not_found, available:[…]}` (§4.3) and `comms_context.py`
skips it with a one-line note (§5.1). Validate-at-write moves the failure **forward** to post
time where the planner context still exists, rather than discovering it only when an executor
hydrates. It is a best-effort gate, not a hard reject: a transient resolve failure (index not
yet built) **must not** fail the task post — on any resolver error the ref is kept as-authored
and the read-side guards remain the backstop. The block-or-empty contract (F9) holds end to
end.

Backward-compat: omitting `context_refs` ⇒ NULL column ⇒ identical to today (§7). A ref that
resolves cleanly is stored byte-identical to what the derivation (§2.1) produced — validation
only ever *relaxes* a dead anchor to whole-file, never tightens a good one.

---

## 3. Anchor convention + section-index build

### 3.1 Anchor convention (locked decision 3)

A section is addressed by a **slug derived from its markdown heading**, plus an optional
explicit escape hatch:

```
Heading                         Slug (anchor)
────────────────────────────    ─────────────
## Phase 3 — Fix path prefixes   phase-3        ← number wins: "phase" + first integer
## Phase 3                       phase-3
### Data layer                   data-layer     ← lowercased, non-alnum → single '-'
## Edge Cases: Phase 1           phase-1        ← "phase N" pattern recognized anywhere
<!-- pathly:anchor id="x" -->    x              ← explicit escape hatch (verbatim id)
```

**Slug algorithm (deterministic, in `runner/sections.py`):**
1. If a `<!-- pathly:anchor id="ID" -->` comment immediately precedes (or opens) the
   section, the anchor is `ID` verbatim. This is the escape hatch for sections whose
   heading doesn't slugify usefully, or two headings that would collide.
2. Else, if the heading text matches `(?i)\bphase\s+(\d+)\b`, the anchor is
   `phase-<N>`. **This is the load-bearing case** — it aligns with
   `IMPLEMENTATION_PLAN.md`'s `## Phase N` headings (`plan.md:162-165`) and the task's
   `Phase N` title (F1), so the planner can mechanically map a phase task to
   `EDGE_CASES.md §phase-N`.
3. Else, generic slug: lowercase, strip a leading `## `/`### `, drop a trailing `— …`
   clause, replace runs of non-`[a-z0-9]` with `-`, trim dashes.
4. **Collision rule:** if two slugs in one file collide, suffix `-2`, `-3` in document
   order, and the build records the collision so the planner is warned (a section it
   meant to reference may have a surprising anchor). The escape hatch (step 1) is the fix.

**Planner authoring requirement (locked decision 3):** the planner MUST author
`EDGE_CASES.md` / `HAPPY_FLOW.md` / `ARCHITECTURE_PROPOSAL.md` with `## Phase N` headings
matching `IMPLEMENTATION_PLAN.md`, so phase-aligned hydration works. This is **step 1 of
the sequencing (§9)** and is nearly free — it is a convention reinforcement in the plan
templates + `plan.md`, not code.

### 3.2 The section index — **new `comms_artifact_sections` table** (per locked decision 3)

| Option | Verdict |
|---|---|
| A. Reuse `comms_artifacts.summary`/`version` only (one row per artifact) | Insufficient alone. `comms_artifacts` is one row per *artifact*; sections are many-per-artifact. There's nowhere to store per-section line-ranges. `summary` stays the artifact-level INDEX summary (F6). |
| **B. New `comms_artifact_sections` table** ✅ | A section is a first-class addressable unit (anchor → line-range + summary + hash). Many-per-artifact, FK to `comms_artifacts.id`, rebuilt on write. Mirrors the existing `comms_artifacts`/`comms_embeddings` side-table pattern. |

**Decision: B, and *also* keep using `comms_artifacts.summary` for the artifact-level
summary (F6).** They are different granularities: artifact-summary (1 per file, the
INDEX-tier catalog entry) vs. section rows (N per file, the HYDRATE addressing table).

```sql
-- migrations.py — add to the CREATE TABLE block (beside comms_artifacts, ~line 265)
CREATE TABLE IF NOT EXISTS comms_artifact_sections (
    id            TEXT PRIMARY KEY,
    artifact_id   TEXT NOT NULL,            -- FK → comms_artifacts.id
    anchor        TEXT NOT NULL,            -- slug or explicit pathly:anchor id
    heading       TEXT,                     -- original heading text (for display)
    line_start    INTEGER NOT NULL,         -- 1-based inclusive
    line_end      INTEGER NOT NULL,         -- 1-based inclusive
    summary       TEXT,                     -- ≤1 sentence; INDEX tier (inference service)
    ordinal       INTEGER DEFAULT 0,        -- document order
    UNIQUE(artifact_id, anchor)
);
CREATE INDEX IF NOT EXISTS idx_artifact_sections_artifact
    ON comms_artifact_sections(artifact_id);
```

Plus two index/staleness columns on `comms_artifacts` (additive, beside `context_refs`):

```python
# migrations.py — _add_additive_migrations(), additional tuples
("comms_artifacts",     "indexed_mtime",         "REAL"),    # st_mtime at last index
("comms_artifacts",     "indexed_hash",          "TEXT"),    # sha256 of file at last index (FULL content)
("comms_artifacts",     "indexed_structure_key", "TEXT"),    # order-independent set of heading slugs at last index
```

`indexed_mtime` + `indexed_hash` are the cheap **content-change** gate; `indexed_structure_key`
is the separate **structural-change** gate that decides whether the *expensive* tier
(summary + embedding) must re-derive. The three are the **stale-index detector** (§3.4) and
together implement the position-invariant re-derivation contract there. Adding
`indexed_structure_key` is one more additive tuple in exactly the F5 pattern — chosen over
recompute-and-compare-on-every-read so the structural trigger is a single stored-value
comparison (`stored == current_structure_key?`), not a re-parse each check.

### 3.3 When/where the index runs (locked decision 3: "at artifact write-time")

The parser lives in `runner/sections.py` (NEW, runner layer — importable by both
`http_server` and `supervisor`, per F11). It is pure: file path in, list of
`(anchor, heading, line_start, line_end, ordinal)` out. It does **no** DB or network I/O.

```python
# src/pathly_orchestrator/runner/sections.py  (NEW)
from dataclasses import dataclass

@dataclass(frozen=True)
class Section:
    anchor: str
    heading: str
    line_start: int          # 1-based inclusive
    line_end: int            # 1-based inclusive
    ordinal: int

def parse_sections(text: str) -> list[Section]:
    """Split markdown into heading-delimited sections. A section runs from its
    heading line to the line before the next heading of equal-or-higher level
    (or EOF). Honors a `<!-- pathly:anchor id=... -->` comment as an explicit
    anchor. Never raises — returns [] for empty/None. Pure (no I/O)."""

def slugify_heading(heading: str) -> str:
    """The §3.1 algorithm. Pure."""

def file_fingerprint(path: str) -> tuple[float, str]:
    """(st_mtime, sha256-hex of FULL content) for staleness detection. Reads once."""

def structure_key(sections: list[Section]) -> str:
    """The order-INDEPENDENT set of heading slugs, as a stable canonical string
    (e.g. sorted slugs joined). Two files with the same headings in any order —
    or the same headings with body text edited or sections reordered — yield the
    SAME structure_key. Adding / removing / renaming a heading changes it. Pure."""
```

The DB write helper lives in `db/queries/comms.py`:

```python
def reindex_artifact_sections(
    conn, artifact_id: str, sections: list[dict],
    mtime: float, content_hash: str, structure_key: str,
) -> None:
    """Replace all section rows for artifact_id (the cheap line-range re-parse),
    then stamp comms_artifacts.indexed_mtime / indexed_hash / indexed_structure_key.
    Idempotent: DELETE then INSERT under the write lock (mirrors store_embedding's
    INSERT OR REPLACE pattern). Does NOT re-summarize or re-embed — that expensive
    tier is fired separately and only when structure_key changed (§3.4)."""
```

**Two trigger points (both already exist as write paths):**

1. **Artifact post / attach** (`comms.py:197-209`, `comms.py:608-620`) — when a
   `type="artifact"` message lands and an `insert_artifact` row is created, also call (in
   the runner layer, best-effort, fire-and-forget like `embed_async`) a
   `index_artifact_async(artifact_id, path)` that parses sections and writes the index +
   the artifact summary (the latter via the inference service, §7-cross-link). This is
   the natural home and needs no new route. **Under Q3=(b) this is the primary path for the
   advisory files** — the planner posts `EDGE_CASES.md`/`HAPPY_FLOW.md`/
   `ARCHITECTURE_PROPOSAL.md` as artifacts in Step 6 (§6 row 7), so each gets its row +
   eager index here at plan time.

2. **Lazy build on first hydrate** (the legacy / defensive case, F7) — with Q3=(b) the
   planner *does* post `EDGE_CASES.md`/`HAPPY_FLOW.md`/`ARCHITECTURE_PROPOSAL.md` as
   `type="artifact"` messages (§6 row 7), so on new plans entry (1) above already created the
   row and index eagerly. But a **legacy plan** (seeded before this feature) — or any by-path
   hydrate of a file that was never posted — has a file on disk with no `comms_artifacts` row
   and no index. The `/section` endpoint therefore **still builds the index on demand** the
   first time such a ref is hydrated: `find_or_create_artifact_by_path` resolves-or-creates a
   minimal row by `(scope, path)` (§6 row 2d), then parse, store, slice. Subsequent hydrates
   hit the cached index unless stale. This is what keeps hydration robust for legacy plans
   and the by-path endpoint (§4.1) — the graceful-degradation path, not the common one (F7).

```
  index build — two entry points, one builder
  ┌─────────────────────────────────────────────────────────────┐
  │  (1) artifact posted   ──► index_artifact_async(id, path)     │
  │      (eager, like embed_async)        │                       │
  │                                       ▼                       │
  │  (2) first /section hydrate ──► ensure_indexed(scope, path)   │
  │      (lazy, legacy/never-posted)      │                       │
  │                                       ▼                       │
  │                       runner/sections.parse_sections(text)    │
  │                       db/...reindex_artifact_sections(...)     │
  └─────────────────────────────────────────────────────────────┘
```

### 3.4 Stale-index handling (locked decision 4 — the sharp edge)

**Principle: the stored index is a CACHE, not a source of truth.** The file on disk is the
only source of truth. Every read *validates the cache against the live file* before serving,
so `/section` can never serve stale content — and crucially, the two halves of the cache
revalidate on **different, independent triggers**:

- **Line-ranges** (`comms_artifact_sections.line_start/line_end`) are revalidated on **any
  content change** and re-parsed *synchronously before the slice* — cheap, deterministic,
  blocking is fine. This is what guarantees `/section` is always correct.
- **Summaries + embeddings** (the INDEX tier — `comms_artifacts.summary`,
  `comms_artifact_sections.summary`, the per-message embedding) are **eventually consistent**:
  re-derived **async / debounced, never eagerly on edit, and nothing ever blocks on them.** A
  read serves the existing (possibly slightly stale) summary while a re-derivation, if one was
  triggered, runs in the background — exactly the fire-and-forget shape `embed_async` /
  `summarize_async` already use (inference §4).

This split is the whole point: keeping `/section` correct is cheap and must be synchronous;
keeping summaries fresh is expensive and must not be on the read path.

**Position-invariant re-derivation — the precise trigger logic.** Two fingerprints gate two
different rebuilds, and they are deliberately independent:

| Fingerprint | What it covers | What a change triggers | Cost |
|---|---|---|---|
| `indexed_hash` | sha256 of the **full file content** | re-parse **line-ranges** (cheap, deterministic, sync-before-slice) | low |
| `indexed_structure_key` | the **order-independent set of heading slugs** | re-summarize + re-embed (the expensive INDEX tier) | high → **async only** |

```
hydrate(anchor):
  read indexed_mtime / indexed_hash / indexed_structure_key
  cur_mtime = os.stat(path).st_mtime
  if cur_mtime == indexed_mtime:                 # fast path — file untouched
      use cached section rows                    # one stat, nothing else
  else:
      cur_hash = sha256(file)
      if cur_hash == indexed_hash:               # mtime moved, content identical (touch/checkout)
          update indexed_mtime; use cached rows
      else:                                       # content genuinely changed
          fresh = parse_sections(file)
          cur_struct = structure_key(fresh)
          # ── ALWAYS: cheap line-range re-parse, synchronous, before slicing ──
          reindex_artifact_sections(... fresh ..., cur_hash, cur_struct)
          slice from the fresh rows               # /section stays correct
          # ── ONLY on structural change: expensive re-derive, ASYNC ──
          if cur_struct != indexed_structure_key:
              schedule_resummarize_and_reembed_async(artifact_id)   # debounced, non-blocking
          #   else: headings unchanged → summary + embedding STILL VALID → no churn
```

**The consequence to state explicitly (the edge case this answers):** **moving or reordering
a section, or shifting a section's position by editing text elsewhere in the file, changes
`indexed_hash` (→ line-ranges re-parse) but does NOT change `indexed_structure_key` → NO
re-summarize, NO re-embed.** The expensive tier fires **only** on a *true structural change* —
a heading **added, removed, or renamed** (a new/dropped/renamed topic). Position is not
structure; the set of topics is. This is the same stability property the topic-map summary was
designed around (DESIGN_SPEC-local-inference §2a) — `structure_key` is its concrete trigger.

- **Borderline case — content edits that shift the topic map.** Editing prose *inside* a
  section can, in principle, change which keywords a topic-map summary would surface even
  though no heading changed. Keep the topic map **structural enough that minor edits don't
  move it** — it is a heading list with a short gloss (inference §2a), keyed on `structure_key`
  (the slugs), not on body keywords. When a body edit genuinely *should* refresh a summary, it
  is picked up the next time `structure_key` changes, or by a low-priority background refresh —
  and either way it is re-derived **async (eventual consistency), never blocking a read.** We
  accept a briefly-stale *summary* (a findability hint) as the cost of never blocking; we never
  accept a stale *slice* (the payload), which is why line-ranges are the synchronous half.

The original §3.4 guarantees still hold, now sharpened by the cache framing:

- mtime is the cheap gate (one `stat`); the hash is computed only when mtime disagrees, and
  `structure_key` only when the hash disagrees — steady state is a single `stat`.
- **Never serve a slice from a stale index.** Line-ranges are re-parsed *before* slicing on
  any content change. If the re-parse fails (file deleted/unreadable mid-edit), the endpoint
  returns a structured `stale`/`missing` error (§4) rather than guessing. (Summaries, being
  eventually-consistent and never the payload, never gate a read this way.)
- If the requested `anchor` no longer exists after a re-parse (the planner renamed the
  heading — which is also exactly a `structure_key` change), return
  `404 {error: "anchor_not_found", available:[...]}` listing current anchors — actionable,
  not silent — and the async re-derive picks up the new structure.

---

## 4. The hydration endpoint

```
GET /comms/artifacts/<artifact_id>/section?anchor=<slug>
```

But see the **resolution note** below: a `context_refs` entry carries `{artifact, anchor}` +
the task's scope but **not** an artifact id, so the endpoint also accepts a **path-based**
form that resolves the row by `(scope, path)` without the caller first knowing an id. Under
Q3=(b) this lookup **now usually finds the row** the planner posted in Step 6; it still
falls back to `find_or_create_artifact_by_path` for legacy / never-posted files (F7, §6
row 2d) so it never crashes.

### 4.1 Params

| Form | Params | Use |
|---|---|---|
| **By id** (artifact already has a row) | path `artifact_id`; query `anchor` (optional → whole file) | Posted artifacts; the `/comms/artifacts` list returns ids. |
| **By path** (the common DAG case — hydrating a `context_refs` entry) | query `feature`/`scope` + `artifact` (basename) + `anchor` | Resolves `path = pathly/plans/<scope>/<artifact>`, looks up the `comms_artifacts` row by `(scope, path)` (usually finds the (b)-posted row; defensively resolves-or-creates one for legacy files, §6 row 2d), ensure-indexes, then slices. |

A single route handles both; if `artifact_id` is present in the path it wins, else the
query `(scope, artifact)` pair is resolved by `(scope, path)` (resolved-or-created for
legacy files). Optional `?format=text` returns `text/markdown` raw (for the editor or a
curl); default is JSON.

### 4.2 Response (200)

```jsonc
{
  "ok": true,
  "artifact_id": "…",
  "artifact": "EDGE_CASES.md",
  "anchor": "phase-3",
  "heading": "## Phase 3 — Fix path prefixes",
  "line_start": 40,
  "line_end": 78,
  "text": "## Phase 3 — Fix path prefixes\n\n- Edge: empty path…\n…",   // FULL section, lossless
  "summary": "Edge cases for the path-prefix fix.",   // INDEX-tier, may be null
  "stale_rebuilt": false                               // true if the index was rebuilt this call
}
```

`text` is the **payload** (HYDRATE tier). `summary` is included only as context; the skill
(§6) tells the agent to read `text`, not `summary`.

### 4.3 Errors / edge cases (locked decision 4)

| Condition | Status | Body |
|---|---|---|
| Missing/blank `anchor` AND not whole-file request | 400 | `{error: "anchor required"}` |
| Neither `artifact_id` nor `(scope+artifact)` resolvable | 400 | `{error: "specify artifact_id or scope+artifact"}` |
| Artifact row absent and path doesn't exist on disk | 404 | `{error: "artifact_not_found", path}` |
| File exists, but `anchor` not found (after any rebuild) | 404 | `{error: "anchor_not_found", available: [...slugs]}` |
| Index stale → rebuilt successfully | 200 | normal body, `stale_rebuilt: true` |
| Index stale → rebuild **failed** (file unreadable mid-edit) | 409 | `{error: "stale_index", detail}` — caller retries; never returns wrong lines |
| Path escapes the plan folder (`..`, absolute outside root) | 400 | `{error: "path_out_of_scope"}` — **path-traversal guard** |

**Path-traversal guard is mandatory.** The path-based form composes a filesystem path from
client input (`artifact` basename). The handler MUST `os.path.normpath`-join under the
resolved `pathly/plans/<scope>/` root and reject anything that escapes it (reuse the
forward-slash normalization already in `comms.py:749`). `artifact` is a basename only —
reject any value containing a separator.

### 4.4 Route sketch (follows the F10 idiom)

```python
@bp.route("/comms/artifacts/<artifact_id>/section", methods=["GET"])
@bp.route("/comms/artifacts/section", methods=["GET"])   # path-based form
def comms_artifact_section(artifact_id: str | None = None):
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.runner.hydrate import hydrate_section as _hydrate
        anchor = (request.args.get("anchor") or "").strip() or None
        scope  = (request.args.get("scope") or request.args.get("feature") or "").strip()
        artifact = (request.args.get("artifact") or "").strip()
        conn = _get_db()
        result = _hydrate(conn, artifact_id=artifact_id, scope=scope,
                          artifact=artifact, anchor=anchor)
        return jsonify(result["body"]), result["status"]
    except Exception as exc:
        logging.exception("comms_artifact_section error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
```

`runner/hydrate.py` (NEW) owns the orchestration: resolve-or-create artifact row →
staleness check (§3.4) → ensure index → slice → build the body/status dict. It imports
`runner/sections.py` + `db/queries/comms.py` (all same-or-lower layer, F11). **It never
raises to the route** (F9 idiom): unexpected failure returns a 500-shaped body, expected
edge cases return the table above.

---

## 5. Three query modes → how they wire into `comms_context.py`

Locked decision 5: **priority order STRUCTURED → HYDRATE → SEMANTIC.** Mapping onto the
existing two-channel block (F9):

```
  retrieve_board_context(topic, project_root, task_description, board_scope)
  ──────────────────────────────────────────────────────────────────────────
   ① STRUCTURED  (deterministic SQL)         → existing  🔒 Governance channel
        get_pending_decisions / get_active_escalations   (comms_context.py:155-164)
        + NEW deterministic task context (goal_id / depends_on / lane) when a
          task_id is in scope.  "Always applies."

   ② HYDRATE     (manifest section fetch)    → NEW  📎 Referenced context channel
        for each entry in task.context_refs:
            GET section text (line-range slice)   ← lossless, the payload
        injected as: "📎 Referenced context (authoritative for this task)".

   ③ SEMANTIC    (per-message embedding, F8)  → existing  💡 Context channel
        search_by_hybrid(task_description, embedding, ...)  (comms_context.py:196)
        "possibly relevant — verify before acting."  Discovery only.
        (The existing per-MESSAGE vector, unchanged. It returns message-level
         pointers — summary/section-level embedding is rejected, not deferred, §8.)
```

### 5.1 What changes in `comms_context.py`

The function today is called with `(topic, project_root, task_description, board_scope)`.
It does **not** currently receive the task being executed, so it cannot read
`context_refs`. The change:

1. **Add an optional `task_id: str | None = None` parameter** (default None ⇒ behaves
   exactly as today — backward-compatible, F9). When present, the function:
   - fetches the task row, reads `context_refs`;
   - for each ref, calls the **in-process** hydrate helper (`runner/hydrate.py`, not an
     HTTP round-trip — `comms_context.py` is in the runner layer and may import it
     directly) to get section text;
   - emits a **new third channel** `### 📎 Referenced context (authoritative for this
     task)` between Governance and the semantic Context channel.
2. **HYDRATE failures are non-fatal**: a ref whose file/anchor is missing is **skipped
   with a one-line note** (`- ⚠ EDGE_CASES.md §phase-9 — section not found`), never an
   exception. The block-or-empty contract (F9) is preserved.
3. **SEMANTIC is unchanged** mechanically and substantively — still
   `search_by_hybrid` over the **existing per-message** embeddings (F8), scoped to the
   exposed boards, returning message-level pointers. It is only **re-labeled** to make the
   priority explicit: it is the *discovery/verify* channel, below the *authoritative*
   referenced channel. (Ranking over *summary*/section-level vectors is **rejected, not
   deferred**, §8 — the call site never changes.)

```
  ## Communication Board
  ### 🔒 Governance (always applies — do not override)      ← ① STRUCTURED
     • <pending decisions / escalations>
  ---
  ### 📎 Referenced context (authoritative for this task)   ← ② HYDRATE  (NEW)
     • EDGE_CASES.md §phase-3
       <full section text>
     • HAPPY_FLOW.md §phase-3
       <full section text>
  ---
  ### 💡 Context (possibly relevant — verify before acting)  ← ③ SEMANTIC
     • <semantic hits over summaries>
```

### 5.2 Who calls it with `task_id`

- The **`loop` executor** path: `scheduler_loop` already knows the task row it is about to
  spawn; thread `task_id` into the prompt-assembly that calls `board_context_for` /
  `retrieve_board_context`.
- The **`single` executor** (drain-dag) runs in a CLI and assembles its own context by
  calling the **HTTP** `/section` endpoint per ref (§6) — it does not import Python. So for
  `single`, the manifest is consumed *by the skill via HTTP*, not via `comms_context.py`.
- The **reviewer**: when a review stage runs for a task/goal, it reads the **same
  `context_refs`** off the task row (decision 2) — either through `comms_context.py`
  (FSM/team path) or via the `/section` endpoint (board-native path). Same refs, same
  sections the builder saw. This is the property that closes the gap for "a reviewer of
  Phase 3."

---

## 5a. The Board Catalog — orientation for taskless agents

§5 covers the **task-driven** path: an executor of a goal-task has a `context_refs`
manifest and hydrates it. But not every agent is executing a goal-task. An **ad-hoc agent,
an explorer, a human typing free-text into the board, or any agent with no `context_refs`**
has no manifest to follow and no `task_id` to thread. Today such an agent has no
deterministic way to learn *what artifacts even exist* on the boards it can see — it would
fall straight through to the fuzzy 💡 semantic channel. That is the wrong tool for
*orientation*: semantic answers "what is *like* my query," not "what *exists* here."

The fix is a **deterministic catalog**: a flat listing of `{path, type, title, summary}`
over the board's artifacts — a **table of contents for the board.** It is the third access
pattern, and like the other two it terminates at the hydration endpoint.

```
  taskless agent (no context_refs, no task_id)
        │
        │  ① GET catalog  ── deterministic SQL over summaries, board-scoped
        ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ path                        type      title         summary    │
  │ EDGE_CASES.md               artifact  Edge cases    "Edge…"    │
  │ ARCHITECTURE_PROPOSAL.md    artifact  Arch proposal "Two-tier…"│
  │ HAPPY_FLOW.md               artifact  Happy flow    "The happy…"│
  │ <message-level descriptions of non-file posts…>                │
  └──────────────────────────────────────────────────────────────┘
        │
        │  ② agent picks what's relevant from the summaries
        ▼
        ③ HYDRATE the chosen sections/files  ── same /section path (§4)
                                                or a plain file read
```

### 5a.1 Summaries only — never inner content

The catalog carries **only the artifact-level `summary`** (the INDEX-tier slot, F6), never
section text. It is a *table of contents, not the documents.* This is what keeps it cheap
enough to inject into any agent's opening prompt: it is bounded by the *count* of artifacts
on the exposed boards, not their *size.* The agent then **hydrates** (step ③) exactly the
entries it judged relevant — through the same `/section` endpoint a manifest ref uses, or a
plain file read for a whole short file. The pointer→payload separation of §1.1 holds
identically: the catalog hands out `{path, type, title, summary}` pointers; `/section`
delivers the bytes.

### 5a.2 Deterministic SQL, not embeddings — it belongs to the v1 spine

The catalog is **plain SQL over `comms_artifacts`**, scoped to the boards exposed to the
agent (it reuses the existing board-scope mechanism in `comms_context.py` — the same
`board_scope` filter the Governance and Context channels already honor, F9). Board/scope
live on `comms_messages` (`migrations.py:220-221`), **not** on `comms_artifacts` (whose
columns are `id, message_id, path, type, title, summary, …`, `migrations.py:251-265`), so
the catalog **JOINs the artifact to its owning message** via the existing
`idx_comms_artifacts_msg` FK (`migrations.py:267`):

```sql
-- the catalog query (deterministic; no vectors, no similarity)
SELECT a.path, a.type, a.title, a.summary
FROM comms_artifacts a
JOIN comms_messages  m ON m.id = a.message_id
WHERE m.board IN (:exposed_boards)      -- board/scope live on the message (F4)
  AND m.scope = :scope
ORDER BY a.type, a.path;
-- (message-level descriptions of non-artifact posts are unioned in the same shape)
```

Because it is deterministic SQL and not a vector search, the catalog is part of the **v1
deterministic spine** (§9 step 3), alongside STRUCTURED, the manifest, and the hydration
endpoint — it is *not* a fuzzy index, and the section-/summary-level vector index that would
sit beside it is **rejected, not deferred** (§8). A board with `summary=NULL` everywhere
still produces a usable catalog (§5a.4).

### 5a.3 The summary's job: the catalog description (single duty)

The economy is that the catalog adds **no new field, no new generation step, and no new
write path** — it *reads `comms_artifacts.summary`, the column the inference service already
fills* (once, DESIGN_SPEC-local-inference). In-plan, that summary has exactly **one job: it
is the catalog description.** It is **not** an embedding source: the existing 💡 discovery
channel embeds **message text** (F8, `embeddings.py` — per-message, `chunk_index=0`), *not*
artifact summaries, and the plan adds no vector over summaries. The artifact summary is only
a *latent* embedding source — it would become one *only if* the section-/summary-level
embedding rejected in §8 were ever revived, which the plan does not do. So in-plan the
summary and the catalog are a single reader of a single INDEX-tier column, not a shared
input to two pipelines.

**Exception — the upload path.** For a **user-uploaded** artifact, the generated summary
is *also* used as the embedded message text (see DESIGN_SPEC-local-inference §3a), so for
uploaded artifacts the summary does double duty — catalog *and* search. This is the
**existing per-message embedding** (F8, `chunk_index=0`) fed the summary instead of the
thin "uploaded X" note — **not** section-level embedding, so it does not revive §8. The
single-duty rule above still holds in general: for **agent-created** artifacts, the
summary is the catalog description only and is never an embedding source.

### 5a.4 Catalog endpoint + backward compatibility

A read-only listing route, following the F10 idiom (lazy import, validate, structured
errors, no SSE — it's a read):

```
GET /comms/artifacts?board=<board>&scope=<scope>
    → { "artifacts": [ {path, type, title, summary}, … ] }   // board-scoped TOC
```

This *extends* the existing `GET /comms/artifacts?message_id=` route (F10) with a
board/scope-scoped listing form — same endpoint family, additive query params. When neither
`message_id` nor `board`/`scope` is given, behavior is unchanged.

**Backward compat (NULL summaries):** an artifact whose `summary` is still NULL (summarizer
off, or not yet indexed — §7) appears in the catalog with `summary: null`; the consumer
**falls back to `path`/`title`** as the description. The catalog therefore works on day one,
before the inference service is wired (§9 step 4), exactly mirroring how HYDRATE works with
NULL summaries (§7). Orientation degrades from "rich one-liner" to "filename + title," never
to "absent."

### 5a.5 The three access patterns, side by side

All three answer "how does an agent reach the right artifact," differ only in *how the
pointer is obtained* and *what kind of pointer it is*, and **none hands the agent content
directly** — each terminates in a deterministic fetch (§1.1):

```
  pattern     driven by      pointer source              pointer → fetch
  ─────────   ───────────    ───────────────────────     ──────────────────
  manifest    a task         context_refs (planner)      section anchor →
              (§2, §5)       — what the planner foresaw   /section (direct)
  catalog     browsing       SQL over summaries (§5a)     section/artifact →
              (taskless)     — board table of contents    /section or file read
  semantic    a query        per-message embedding (F8)   message-level → browse
              (§5 ③)         — what the planner missed     catalog / hydrate
  ─────────────────────────────────────────────────────────────────────────
        all three ──►  deterministic fetch (/section · file read)  ──►  full text
```

Manifest is **task-driven and authoritative** (section anchor, straight to `/section`);
catalog is **browse-driven taskless orientation** (section/artifact pointer); semantic is
**query-driven discovery** over the existing per-message embedding (a *message-level*
pointer the agent then resolves by browsing the catalog or hydrating that artifact's
sections). The manifest tells an executor exactly which sections its phase needs; the
catalog lets a manifest-less agent see the whole board and choose; semantic catches
relevance the planner never anticipated. None of them hands the agent content directly —
each yields a pointer that a deterministic fetch resolves.

### 5a.6 Scaling the catalog — goal-hierarchy first, then ranking

The flat board-scoped catalog (§5a.4) is the right shape for a **small board**: a dozen
artifacts fit in one scannable listing an agent reads top-to-bottom. It does not scale to a
**large, aging, multi-goal board** — a flat list of hundreds of `{path, type, title, summary}`
rows is itself a context-budget problem, the very thing the INDEX tier exists to avoid. Two
**additive** moves keep orientation bounded as a board grows, both reusing structure that
already exists — neither introduces a vector or revives §8:

1. **Browse goals first, then a goal's artifacts (the common case at scale).** The board is
   already a **Board → Goals → per-goal Task-DAG** hierarchy (`goal_id` on `comms_messages`,
   F4; GOALS-DAG-EXECUTORS). So a large catalog is browsed in **two bounded steps**: list the
   *goals* (a short set), then list **that goal's** artifacts (bounded by one goal's scope),
   rather than every artifact on the board at once. The goal hierarchy is the natural index —
   the same `goal_id` filter STRUCTURED mode (§5 ①) already uses — and it bounds the *common*
   case for free, because an agent oriented to a goal rarely needs the whole board.

   ```
   small board                large/aging board
   ───────────                ─────────────────
   GET catalog (flat)         GET catalog/goals      ──► [Goal A, Goal B, Goal C …]
     → all artifacts                 │  pick the relevant goal
       (scannable)                   ▼
                              GET catalog?goal_id=A  ──► A's artifacts only (bounded)
   ```

2. **Rank + paginate within a listing (true scale).** Where even a single goal (or a
   goal-less board) holds too many artifacts, the listing returns a **ranked, paginated**
   result instead of the full set — `ORDER BY` recency (`created_at`/`last_edit_at`,
   DESC) for plain browse, or, when the agent has a task string, an **FTS5 keyword match of
   that task against the existing message FTS** (`comms_fts`, §8 item 2 — already
   compiled-in and proven) to surface the artifacts whose messages best match, `LIMIT N`. This
   reuses the deterministic engines already present; it adds **no** new index and **no**
   vector. The catalog query (§5a.4 / §6 row 2f) gains optional `goal_id`, `order`, `limit`,
   `offset` params — additive, the flat board-scoped form unchanged when they are omitted.

**Framing (and why this is correctly deferred-shaped):** the **goal hierarchy bounds the
common case now** — it is structure the board already has, so two-step goal-then-artifact
browse is essentially free and can ship with §5a if wanted. **Ranked/paginated listing + a
section-level keyword index handle *true* scale** — and those are needed *only* at scale, on a
large aging multi-goal board that does not yet exist for most features, which is exactly why
the heavier slice (a new section-level FTS5 over plan text) is the **deferred next step**
documented in §8 item 1's caveat + item 2, **not** a v1 deliverable. v1 ships the flat catalog
(§5a.4); the goal-hierarchy bound is the cheap first scaling move; ranked/paginated + deferred
FTS5 are the documented path the day a board outgrows both. None of this is vector search — it
is the same deterministic spine, indexed by a hierarchy the board already carries.

---

## 6. All call-site changes

Ordered by layer (db → runner → http_server → skills), each independently testable.

| # | File | Change |
|---|---|---|
| 1 | `db/migrations.py` | Add `comms_messages.context_refs TEXT`, `comms_artifacts.indexed_mtime REAL`, `comms_artifacts.indexed_hash TEXT`, `comms_artifacts.indexed_structure_key TEXT` to `_add_additive_migrations` (`:380`). Add `CREATE TABLE comms_artifact_sections` + its index to the `executescript` block (`~:265`). All additive/idempotent. |
| 2 | `db/queries/comms.py` | (a) `post_message` gains `context_refs` kwarg (JSON-encoded, mirrors `depends_on`). (b) NEW `reindex_artifact_sections(conn, artifact_id, sections, mtime, hash, structure_key)` — replaces section rows (cheap line-range re-parse) and stamps `indexed_mtime`/`indexed_hash`/`indexed_structure_key`; does NOT re-summarize/re-embed (that fires async, only on `structure_key` change, §3.4). (c) NEW `get_artifact_sections(conn, artifact_id)` and `get_section(conn, artifact_id, anchor)` — the latter also backs validate-at-write (§2.4). (d) NEW `find_or_create_artifact_by_path(conn, scope, path)` — a **minimal defensive resolver** (no longer the primary mechanism, since Q3=(b) gives advisory files real rows via the Step-6 artifact posts). It resolves the `comms_artifacts` row by `(scope, path)` and creates a minimal row **only if one is missing** — the residual cases being legacy plans seeded before this feature, or a by-path hydrate (§4.1) of a file that was never posted. Keeping it minimal keeps lazy indexing (§3.3) and the by-path endpoint robust without crashing on those rows. (e) `update_artifact_summary` / `update_section_summary` writeback hooks for the inference service. (f) NEW `list_artifacts_catalog(conn, scope, exposed_boards, *, goal_id=None, order=None, limit=None, offset=None)` — the **Board Catalog** query (§5a): `SELECT a.path, a.type, a.title, a.summary FROM comms_artifacts a JOIN comms_messages m ON m.id=a.message_id WHERE m.board IN (exposed) AND m.scope=?` (board/scope live on the message, F4), deterministic, summaries-only. The optional `goal_id`/`order`/`limit`/`offset` params are the **§5a.6 scaling path** (goal-scoped + ranked/paginated browse); omitting them yields the flat board-scoped listing unchanged. Re-export from `db/__init__.py`. |
| 3 | `runner/sections.py` (NEW) | `parse_sections`, `slugify_heading`, `file_fingerprint` (§3.3). Pure markdown logic, no I/O except `file_fingerprint`. |
| 4 | `runner/hydrate.py` (NEW) | `hydrate_section(conn, *, artifact_id, scope, artifact, anchor)` and `ensure_indexed(conn, scope, path)` — orchestration + staleness (§3.4: cheap line-range re-parse synchronous-before-slice on `indexed_hash` change; expensive re-summarize/re-embed scheduled **async only** on `indexed_structure_key` change) + the result/status dict (§4.2/4.3). Never raises. `index_artifact_async(artifact_id, path)` daemon-thread eager indexer (mirrors `embeddings.embed_async`). |
| 5 | `runner/comms_context.py` | Add optional `task_id` param; when set, read `context_refs`, hydrate each ref in-process, emit the new `### 📎 Referenced context` channel between Governance and Context (§5). Failures skipped with a note. Default `task_id=None` ⇒ identical to today. Thread `task_id` through `board_context_for`. |
| 6 | `http_server/blueprints/comms.py` | (a) `/comms/post`: accept + validate `context_refs` — both the **shape** guard and the **validate-at-write** resolution gate (resolve each `{artifact, anchor}`, relax unresolved → whole-file + board-nudge warning, best-effort, §2.4). (b) NEW `GET /comms/artifacts/<id>/section` + `GET /comms/artifacts/section` (path form) → `runner.hydrate.hydrate_section` (§4). (c) In the `type="artifact"` post/attach branches (`:197-209`, `:608-620`), fire `index_artifact_async(artifact_id, path)` (best-effort, after `insert_artifact`). (d) NEW board/scope-scoped listing form on the existing `GET /comms/artifacts` route → `list_artifacts_catalog` (§5a.4); additive query params (`board`/`scope`, plus the optional §5a.6 scaling params `goal_id`/`order`/`limit`/`offset`), `message_id` form unchanged. |
| 7 | `core/skills/planning/plan.md` | **Step 6**: (i) **post each advisory file as an artifact (Q3=(b))** — before/alongside posting the phase tasks (and **before** the task posts, so the section index exists for validate-at-write, §2.4), the planner posts `EDGE_CASES.md`, `HAPPY_FLOW.md`, and `ARCHITECTURE_PROPOSAL.md` as `type="artifact"` messages via the existing artifact-post path (which creates the `comms_artifacts` row + fires `embed_async` + indexes), capturing each returned `message_id`. (ii) add `context_refs` to the per-phase task POST. **`context_refs` are DERIVED, not hand-authored (§2.1):** the skill instruction is *"for each `## Phase N` in `IMPLEMENTATION_PLAN.md`, emit `[{EDGE_CASES.md, phase-N}, {HAPPY_FLOW.md, phase-N}]` (+ optional `ARCHITECTURE_PROPOSAL` per §10 Q1) on that phase's task"* — a mechanical phase→anchor mapping over headings the planner already wrote, **not** a free-hand authoring step. The model's authoring duty is only the consistent `## Phase N` headings (next sentence + row 10). Minimally `[{artifact:"EDGE_CASES.md", anchor:"phase-N"}, {artifact:"HAPPY_FLOW.md", anchor:"phase-N"}]` when those files exist (standard/strict). The post path then **validate-at-writes** each ref against the just-built index (§2.4): an unresolved anchor is relaxed to whole-file (`anchor:null`) + a board nudge, never silently dropped. **Also (sequencing step 1):** add an authoring instruction that `EDGE_CASES.md` / `HAPPY_FLOW.md` / `ARCHITECTURE_PROPOSAL.md` use `## Phase N` headings matching `IMPLEMENTATION_PLAN.md` — this is the *one* thing the LLM must get right for derivation to work. Keep the idempotency guard + fail-silent branch (both the artifact posts and the task posts skip cleanly on a re-run / failed board; a validate-at-write resolver error keeps the ref as-derived, §2.4). **Propagate:** `pathly-setup claude --apply --repair ; python -m build`. |
| 8 | `core/skills/development/drain-dag.md` | **Step 3 (Do the work)**: after reading `artifact_path`, add: "If the task has `context_refs`, for each `{artifact, anchor}` call `GET /comms/artifacts/section?scope=$SCOPE&artifact=<artifact>&anchor=<anchor>` and read the returned `text` (the full section) — this is the advisory spec (edge cases, happy flow) for your phase. The `summary` is a pointer, not the spec; read `text`." Same propagation. |
| 9 | `core/skills` (reviewer skill) | Mirror the drain-dag instruction so a reviewer hydrates the **same** `context_refs` off the task it is reviewing (decision 2). Same propagation. |
| 10 | `core/templates/plan/{EDGE_CASES,HAPPY_FLOW,ARCHITECTURE_PROPOSAL}.template.md` | Reinforce `## Phase N` headings so generated artifacts are anchor-addressable (sequencing step 1, nearly free). |

**Layer-violation check** (against `pathly_orchestrator/CLAUDE.md`):

```
db/         reindex/get_section/find_or_create_artifact_by_path — no upward imports. OK.
runner/     sections.py (pure) ; hydrate.py imports db.queries.comms (lower). OK.
            comms_context.py imports runner.hydrate (same layer). OK.
http_server comms.py route lazily imports runner.hydrate inside the handler
            (matches every other comms route). OK.
renderer    NO CHANGE. Editor "Ask Agent" untouched (F11). OK.
```

---

## 7. Backward compatibility

Every new path degrades to today's behavior:

| Legacy condition | Behavior |
|---|---|
| Task with **no `context_refs`** (every task seeded before this ships) | `context_refs` is NULL. `comms_context.py` with `task_id` set finds no refs ⇒ emits no 📎 channel ⇒ block is byte-identical to today. `drain-dag` skips the hydrate step. |
| `comms_context.py` called **without `task_id`** (every existing caller) | Default `None` ⇒ exact current two-channel output. No caller is forced to change. |
| Artifact with **no section index** (never indexed, or pre-feature) | First `/section` hydrate lazily builds it (§3.3 entry 2). No migration/backfill needed. |
| Plan artifact **never posted as `type="artifact"`** (**legacy-only** since Q3=(b); F7) | New plans post advisory files as artifacts in Step 6 (§6 row 7), so they have rows + indexes eagerly — this is **no longer the common case**. A **legacy plan** seeded before this ships has no artifact rows and its tasks have no `context_refs`, so it **degrades to today's behavior**: the agent reads the files directly (file-reading model), the files simply don't appear in the Board Catalog and aren't hydratable via `/section` until/unless touched. If a legacy `context_refs` or a by-path hydrate *does* reach such a file, `find_or_create_artifact_by_path` defensively resolves/creates a minimal row on first hydrate (§6 row 2d) so the endpoint never crashes. |
| **Summarizer not configured** (inference backend = minilm / off, per inference spec) | `comms_artifacts.summary` and section `summary` stay NULL. INDEX-tier summary is absent, but **HYDRATE still returns full section text** (it slices the file, not the summary, F6). The 📎 channel is unaffected; only the 💡 semantic ranking quality is reduced. The two specs are decoupled here on purpose. |
| **Board Catalog with NULL summaries** (summarizer off, or artifact not yet indexed) | `list_artifacts_catalog` returns the row with `summary: null`; the consumer **falls back to `path`/`title`** as the description (§5a.4). The catalog is usable on day one, before the inference service is wired (§9 step 4). Orientation degrades to "filename + title," never to absent. |
| **Taskless / ad-hoc agent** (no `context_refs`, no `task_id`) | Gets no 📎 channel (correct — there is no manifest). Orients via the deterministic catalog (§5a) instead of the fuzzy 💡 channel, then hydrates its picks through the same `/section` path. |
| **sqlite-vec / FTS unavailable** | SEMANTIC degrades to recency exactly as today (`comms_context.py:204-207`); STRUCTURED + HYDRATE are unaffected (they're plain SQL + file reads). |

---

## 8. Scope guard — what NOT to build

**`.md` only — every other artifact type is DEFERRED (the hard boundary).** v1 of the
section/anchor model processes **only Markdown (`.md`) artifacts**. The entire mechanism in
this spec — the heading-derived anchor convention (§3.1), `parse_sections` and the
`comms_artifact_sections` index (§3.2–§3.3), the topic-map summary it consumes (§1, §2a of
the inference spec), and the `/section` hydration endpoint (§4) — is **markdown-heading-based**
and therefore applies **only to `.md`**. **Images, PDFs, plain text (`.txt`), code, and any
other type are explicitly DEFERRED to a separate later effort** — they have no headings, so
they have no chapters to anchor, index, or hydrate. This is item 0 because it gates
everything else; see the dedicated guard below.

**Semantic discovery is the existing message-level embedding, and nothing more.** The
discovery channel is exactly today's `search_by_hybrid` over **per-message** embeddings
(F8), scoped to the exposed boards. The plan builds **no** section-level embeddings and
**no** new artifact/section FTS5 index. These are not a later phase — they are **rejected
outright** (item 1 below). The deterministic spine (§9.1) is the whole plan; there is no
end-state queued behind it. This boundary is stated up front so no one mistakes the plan
for the front of a longer roadmap.

0. **`.md` only — section model does not run for any other type (DEFERRED).** The
   anchor/section/hydration model is **heading-based**, and only Markdown has headings, so
   v1 fully processes **only `.md` artifacts**. Concretely:
   - **`parse_sections` / `slugify_heading` (§3.1, §3.3), the `comms_artifact_sections`
     index (§3.2), and the `/section` endpoint (§4) run for `.md` artifacts only.** For a
     non-`.md` artifact they do **not** run — there is no section index, no anchor, and no
     `/section` hydration. The eager `index_artifact_async` (§3.3) and lazy
     `ensure_indexed` (§4.1) both **early-return for non-`.md`** before parsing; a
     `context_refs` entry pointing at a non-`.md` artifact has no anchor to resolve and is
     skipped with a one-line note (the §5.1 non-fatal-skip path).
   - **A non-`.md` artifact may still be a board *card*.** It can be posted as a
     `type="artifact"` message and appear in the **Board Catalog** (§5a) as a
     `{path, type, title}` row — but in v1 it gets **no topic-map summary, no section index,
     and no section hydration** (its `summary` stays NULL → the catalog falls back to
     `path`/`title`, §5a.4). It is findable and openable as a whole file; it is not
     chaptered.
   - **Images, PDF, `.txt`, code, and everything else are DEFERRED to a separate later
     effort** — not parked inside this feature. This mirrors the inference spec's matching
     `.md`-only boundary (DESIGN_SPEC-local-inference §6): summarization (the topic map) also
     runs only for `.md`, so the two specs agree on the same hard line. If chaptering ever
     extends to another type, that is new design work, not a v1 toggle.

1. **Section-level embeddings — rejected, not deferred.** The plan embeds **only the
   per-message vector that already exists** (F8) — NOT section summaries, NOT per-paragraph
   chunks, NOT artifact summaries as separate embedding rows. This is a removed idea, not a
   parked one. Four reasons:
   - **(a) The Board Catalog (§5a) already gives complete, deterministic visibility.** Every
     artifact is listed `{path, type, title, summary}`. A capable agent browsing the catalog
     does not *miss* an artifact — there is nothing for similarity to surface that the
     deterministic table of contents has not already named.
   - **(b) Discovery is already covered.** The existing per-message embedding (F8) plus the
     existing message-level FTS5 (`comms_fts`, F9) are both in production and both run today.
     Section vectors would be a third discovery mechanism layered over two that already work.
   - **(c) It carries a standing pipeline cost.** Section vectors must be re-embedded on
     every artifact edit — a recurring cost paid against value that only materializes on a
     large, aging, multi-goal board, which is not the common case.
   - **(d) A standing "deferred end-state" creates design gravity.** Keeping it on the page
     as a future phase pulls reviewers and builders toward it and **misrepresents what is
     actually being built** — the deterministic spine is the entire feature.

   **Caveat (record this for any future revisit):** if board-scale discovery ever *does*
   prove insufficient, the cheaper next step is **section-level FTS5 keyword** — reusing the
   already-compiled-in engine (`comms_fts` proves it works, item 2) — **not vectors.** Start
   from keyword, not embeddings. *And if ever revisited, never embed
   `IMPLEMENTATION_PLAN.md` / `FEATURE_INDEX.md` / `PROGRESS.md` — they are the source of the
   manifest and are already covered 1:1 by `context_refs` and the DAG; only the advisory
   artifacts (`EDGE_CASES` / `ARCHITECTURE_PROPOSAL` / `HAPPY_FLOW` / `USER_STORIES`) would
   ever warrant it.* Do not touch `store_embedding`'s per-message `chunk_index=0` model.
2. **No *new* artifact/section-level FTS5 index.** Message-level FTS5 **already exists and
   already runs** — `comms_fts` indexes `comms_messages.text` (`migrations.py:285-300`) and
   `/comms/search` already fuses it with vectors (the existing hybrid, F8/F9). So FTS5 *as a
   capability is present and proven compiled-in today*. What the plan does **not** add is a
   *new* FTS index over **artifact/section text** (today's `comms_fts` covers messages, not
   the plan files). Per item 1's caveat, a section-level keyword index — reusing this same
   already-available engine — is the *cheapest* place to start **if** discovery ever proves
   insufficient; it is the documented next step, not a planned one. Keyword needs today are
   met by the existing message FTS + STRUCTURED SQL + the deterministic catalog (§5a).
3. **No editor rerouting.** The editor "Ask Agent / Explain" stays renderer-PTY only
   (F11, inference spec §0). This feature is Python-side; it does not give the renderer a
   new Python call. The `/section` endpoint may *incidentally* be useful to the editor
   later, but wiring that is out of scope.
4. **No cross-artifact dedup / synthesis.** If two refs point at overlapping content, both
   are hydrated as-is. Consolidation/fan-in is explicitly ROADMAP "deferred polish".
5. **No artifact write-back / versioning hooks.** `version`/`supersedes`/`last_edit_*`
   stay as the ROADMAP follow-up. This spec only *reads* artifacts and *indexes* sections;
   it adds `indexed_mtime`/`indexed_hash`/`indexed_structure_key` (read-side staleness +
   the structural-change re-derive trigger, §3.4) but does NOT implement edit-versioning.
   (Decision 6's write-isolation guarantee is *stated* here, *enforced* by that later
   work — see §10 Q4.)
6. **No new embedding model / no re-embedding existing messages.** Reuse MiniLM-384 as-is.
7. **No runtime auto-discovery of refs.** `context_refs` are **derived deterministically
   from the plan's `## Phase N` structure at Step 6** (§2.1), not hand-authored free-hand by
   the planner LLM and not inferred at *runtime*: v1 does NOT infer "phase 3 task ⇒
   EDGE_CASES §phase-3" when the task runs — the planner does the phase→anchor mapping once,
   by parsing structure at plan time, and the runtime just follows the stored ref. (The LLM's
   only authoring duty is consistent headings; the mapping itself is mechanical, §2.1.)
   Runtime / dynamic ref inference is a possible deferred-phase extension.
8. **No deletion/GC of section rows.** Reindex replaces a file's rows; orphaned rows from
   deleted artifacts are harmless and left for a later sweep.

**Scale note — the catalog's growth path is bounded, and the heavy slice is correctly
deferred.** The flat Board Catalog (§5a.4) is sized for a small board. As a board grows large
and aging, orientation stays bounded **without new fuzzy machinery** by §5a.6: browse **goals
first** then a goal's artifacts (using the Board→Goals→DAG hierarchy the board already carries,
F4), and return **ranked/paginated** listings (`ORDER BY` recency, or an FTS5 keyword match of
the task against the *existing* message FTS, `LIMIT N`). The goal hierarchy bounds the **common
case now** and is essentially free; ranked/paginated + a **new section-level FTS5 keyword
index** handle *true* scale and are needed **only** at scale — which is exactly why the
section-level keyword index is the **deferred next step** (item 1's caveat + item 2), not a v1
build, and why **section-level *vectors* remain rejected outright** (item 1) rather than queued
behind it. Start from the hierarchy, then keyword; never vectors.

---

## 9. Sequencing (does NOT block the P1 dispatcher)

The P1 dispatcher (`PHASE-1-dispatcher.md`) is **already shipped** (`single`+`loop`+`team`
landed 2026-06-17). This feature rides *beside* it. Steps 1–2 do not touch any dispatcher
or scheduler code.

**v1 = the deterministic spine + the existing discovery channel.** Everything v1 builds is
either deterministic (STRUCTURED SQL, the `context_refs` manifest, the section index, the
hydration endpoint, the Board Catalog) or *already in production* (the per-message embedding
discovery channel, kept as-is and scoped to the exposed boards). v1 introduces **no new
fuzzy machinery** — it makes the *deterministic* paths reach the advisory artifacts that the
file-reading builder used to reach, and leaves the discovery channel exactly where it is.
Summaries throughout are produced by the inference service (cross-link), and every v1 step
works with `summary=NULL` until that lands (§7).

```
        THE WHOLE PLAN — DETERMINISTIC SPINE + EXISTING DISCOVERY
 step 1  ──►  step 2  ──►  step 3  ──────────────►  step 4
 headings    context_refs  endpoint + write-index   wire the
 (free)      (data only)   + Board Catalog          summarizer
                           (KEEP message embedding   (inference)
                            as discovery channel)
 │           │             │                         │
 └ no P1     └ no P1       └ runner + http_server     └ cross-link
   touch       touch         (deterministic only)        inference
 ───────────────────────────────────────────────────────────────────
        nothing is deferred after step 4 — this is the entire feature
        (section-level vectors are rejected outright, not queued — §8)
```

### 9.1 v1 — build now (deterministic spine + existing discovery)

| Step | Deliverable | Touches P1? | Notes |
|---|---|---|---|
| **1. Planner authors `## Phase N` headings** | `plan.md` + 3 templates reinforce phase-aligned headings in `EDGE_CASES`/`HAPPY_FLOW`/`ARCHITECTURE_PROPOSAL`. | **No** | Nearly free — convention text only, no code. Makes future hydration possible. Ship first. |
| **2. Add `context_refs`** | Migration (1 column) + `post_message`/`/comms/post` accept it + `plan.md` Step 6 emits it. | **No** | Pure additive data plumbing, mirrors the 0b `goal_id`/`executor` change. Tasks now *carry* the link even before anything consumes it. |
| **3. Section endpoint + write-time index + Board Catalog** | `runner/sections.py`, `runner/hydrate.py`, `comms_artifact_sections` table, `GET …/section` (lazy+eager index, staleness), **`list_artifacts_catalog` + the board-scoped `GET /comms/artifacts` listing (§5a)**, and **KEEP the existing per-message embedding** (`search_by_hybrid`, F8) as the 💡 discovery channel, scoped to exposed boards. | No (db + runner + http_server only) | The HYDRATE tier + the catalog go live; the deterministic spine is complete. `drain-dag`/reviewer skills add the hydrate step. Usable end-to-end with summaries=NULL (catalog falls back to path/title, §5a.4). |
| **4. Wire the inference summarizer** | Call the inference service (DESIGN_SPEC-local-inference) at index time to fill `comms_artifacts.summary` + section `summary`; this is the catalog *description* (§5a.3) and is included in the `/section` HYDRATE response. (For **agent-created** artifacts it is **not** an embedding source — the 💡 channel embeds message text, F8.) On the **upload path** the attach UI also exposes the per-upload backend picker (Off/Local/Haiku) and **embeds the generated summary** as the per-message text so it powers the 💡 search channel — see DESIGN_SPEC-local-inference §3a (artifact-level, the existing per-message channel, not section-level §8). | No | **Cross-link only — do not redesign the summarizer.** Improves catalog orientation; HYDRATE and the catalog already worked without it. |

**The P1-safety argument:** steps 1–2 add a column and skill text; the dispatcher reads
neither `context_refs` nor section rows, so it is untouched. Steps 3–4 add new
db/runner/http_server modules and skill *additions* (the hydrate step is appended to
`drain-dag` Step 3; the existing loop is unchanged). The scheduler/`goal_run`/`board_run`
code is never edited — and neither the catalog nor the kept message-embedding touches the
dispatcher or scheduler. A task with no `context_refs` runs exactly as it does today (§7).

---

## 10. Resolved decisions

All four questions below were confirmed by the human on **2026-06-18** with the
recommended answers. The reasoning is preserved; each is now a settled entry, not an open
question. Q3 is the one that rippled — its propagation is reflected in §3.3, §4.1, §6
(rows 2d + 7), and §7.

**Q1 — `context_refs` granularity authored by the planner.**
v1 has the planner emit `{artifact, anchor:"phase-N"}` for `EDGE_CASES`/`HAPPY_FLOW` per
phase (mechanical, cheap). The question was whether it should *also* attempt
`ARCHITECTURE_PROPOSAL` sections (which are often *not* phase-keyed — e.g. `## Data layer`).

> **RESOLVED (2026-06-18): yes, but optional.** The planner always emits
> `{artifact, anchor:"phase-N"}` for `EDGE_CASES`/`HAPPY_FLOW` per phase. For
> `ARCHITECTURE_PROPOSAL` it adds a *section* ref only when a phase clearly maps to a named
> arch section; otherwise it adds a **whole-file ref** (`anchor:null`) for short proposals.
> Whole-file refs hydrate the entire file into the 📎 channel — fine for a 1-page proposal,
> wasteful for a 10-pager, so they are reserved for short artifacts.

**Q2 — `single`-executor hydration: per-ref HTTP calls vs. pre-assembled block.**
The `drain-dag` (single) agent runs in a CLI and would hydrate by calling `/section` once
per ref (§6 row 8). The alternative was to have the dispatcher pre-hydrate all refs into
the spawned prompt (like `comms_context.py` does for `loop`), so the single agent gets the
sections inline and makes zero HTTP calls.

> **RESOLVED (2026-06-18): per-ref HTTP `/section` calls** for the `single` agent — lazy,
> the agent decides whether to hydrate after reading the catalog/summary. **Not**
> pre-assembled into the spawn prompt. This keeps the agent in control of *when/whether* to
> hydrate (it may decide a ref is irrelevant after reading the summary) and avoids bloating
> the spawn prompt with sections it might not need, trading prompt-size for round-trips.
> (§6 row 8 already states this — confirmed.)

**Q3 — How to anchor a `comms_artifacts` row for a plan file (F7).**
`comms_artifacts.message_id` is `NOT NULL` (`migrations.py:253`). Before this decision a
plan artifact that was never posted as a `type="artifact"` message had no message to point
at. Options were: (a) relax `message_id` to nullable (a NOT NULL constraint — needs a table
rebuild on SQLite, not a simple ADD COLUMN); (b) have the planner post one
`type="artifact"` message per advisory file in Step 6 (a real `message_id`, a board card,
and a free `embed_async`, at the cost of N posts + N board cards per plan); (c) synthesize a
single `plan:<scope>` umbrella message and hang all plan-artifact rows off it.

> **RESOLVED (2026-06-18): option (b).** In `plan.md` Step 6 the planner posts each advisory
> file (`EDGE_CASES.md`, `HAPPY_FLOW.md`, `ARCHITECTURE_PROPOSAL.md`) as a `type="artifact"`
> message, capturing each returned `message_id`. Reusing the existing `type="artifact"` post
> path gives every advisory file a real `comms_artifacts` row (+ summary + `embed_async` +
> catalog card) for free, and the `/comms/artifacts` list shows it — the file *becomes* a
> first-class board artifact, exactly consistent with the existing model. (a) is a schema
> rebuild we avoid; (c) is a hidden special-case.
>
> **This is the decision that ripples.** Because advisory files now have real rows,
> `find_or_create_artifact_by_path` is no longer the primary mechanism — it is downgraded to
> a minimal **defensive** resolver for legacy plans (§6 row 2d), and "never posted as
> `type="artifact"`" stops being the common case and becomes a legacy-only graceful-
> degradation path (§7). See §3.3, §4.1, §6, §7.

**Q4 — Scope of the write-isolation/versioning guarantee in v1.**
Decision 6 (agents post new *versions*, never overwrite) is *stated* here but its
enforcement (the `version`/`supersedes` write hooks) is ROADMAP-deferred (§8 item 5). In
v1, two agents editing the same plan file is already prevented by lanes (disjoint file
sets, DAG-SCHEDULER §2.1) — so the guarantee holds *operationally* for tasks but isn't
*enforced* at the artifact layer.

> **RESOLVED (2026-06-18): yes — ship with write-isolation resting on the lane invariant.**
> Artifact-level versioning (`version`/`supersedes` write hooks) stays the separate ROADMAP
> follow-up it already is (§8 item 5). Coupling this feature to versioning would balloon its
> scope for no retrieval benefit. (§8 item 5 already states this — confirmed.)
