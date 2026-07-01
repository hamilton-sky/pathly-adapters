# Unified CLI Composition — Architecture Brief (strawman)

> **Status:** strawman for PO → architect → designer review.
> **Author:** Claude (engineering), grounded in a full code map of the fragments/composition system.
> **One line:** every CLI-engine invocation in Pathly should assemble its prompt through the **same fragment-composition primitive**, so every agent connects to the board the same way.

---

## 1. The problem — two worlds

Every CLI action ultimately hits the same low-level spawn scheduler (`studio/src/main/ipc/terminal.ts`). But the **prompt-composition layer above it is forked in two**, and that fork is the root of the inconsistency the summary/codex bugs exposed.

| World | Paths | Composes fragments? | Board context | Posts progress | Result capture |
|---|---|---|---|---|---|
| **A — Server/FSM** | Evaluate, board single-run, goal-execute *team* | ✅ via `compose_skill` | ✅ `comms_context` | ✅ `comms-post`/`progress-logging` | `AGENT_DONE.summary` (authoritative) |
| **B — Client/Python-direct** | artifact **Summary**, editor **Analyze**, editor **Split**, goal **Decompose**, goal-execute *loop* | ❌ bare prompt | ❌ | ❌ | three incompatible ad-hoc mechanisms |

World B ships **bare prompts** built inline (`buildSummarizePrompt` / `buildAnalyzePrompt` / `buildSplitPrompt`, and a hand-coded decompose POST in `goal_run.py`). Each invents its own result capture:
- **Summary** → in-process `result.text` (the PTY stdout *tail* for engines → mangled; codex chrome leaks in)
- **Analyze / Split** → **file write + poll** (clean — the agent writes `.analysis`/`.split.draft`, the host polls it)
- **Decompose** → Python-side parse

**The cleanest of the three already exists in the codebase:** the editors' file-write-then-poll. That is the capture contract the others should converge on.

---

## 2. The mechanism we build on — fragments

Fragments (`src/pathly_data/core/skills/fragments/*.md`) are reusable prompt blocks stitched onto skill bodies by `composition.yaml` + `compose.py`. They ARE "how an agent connects to Pathly":

| Fragment | Pathly integration it injects |
|---|---|
| **comms-post** | board write — `POST /comms/post` (decision/discovery/warning/**artifact**/question) |
| **progress-logging** *(the only default)* | phase telemetry — `record-phase PHASE_START/DONE` |
| **catalog-pull** | mid-run context read — `GET /comms/artifacts/section` |
| **completion-report** | authoritative result — `AGENT_DONE` (summary, tokens, cost) |
| **feedback-protocol** | feedback-file gate + 3-tier escalation |
| **spawn-rules** *(gated on `can_spawn`)* | sub-agent delegation |
| **scout-choreography** | three-phase parallel context gather |

Composition contract (`compose.py:232-261`): `assembled = strip_frontmatter(skill body) + defaults + per-skill fragments (gated by adapter caps)`. **DB-overridable** per project via the `skill_composition` table. A skill **absent** from the manifest is loaded **raw** (no fragments).

> **Terminology (settled downstream):** *fragment* = atomic block · *skill* = task body · *profile* = the context-selected fragment bundle (`standalone-transform` vs `goal-backed`). The design renames the manifest's `blocks:` → `profiles:` and selects the profile by `goal_id` presence rather than a code branch. See [ORCHESTRATION_MODEL.md](ORCHESTRATION_MODEL.md) › Vocabulary and [DESIGN.md](DESIGN.md) › Architecture › Naming.

**Coverage today:** 19 of ~52 skills converted; **33 raw.** The raw skills that *write to the board but compose nothing* are the real gaps: `development/drain-dag`, `team/architect`, `team/research`.

---

## 3. The thesis

> Extend `compose_skill` to the **client**: the Studio CLI bridge (`cliEngine`/`aiRouter`) stops sending raw text and instead requests a **composed** skill from the same DB-overridable manifest. Then *every* action — summary, analyze, split, evaluate, single-run, decompose, execute — assembles its prompt the same way (skill body + gated fragments), with board context, progress logging, board posting, and result capture injected **declaratively** instead of re-implemented per call-site.

Two load-bearing decisions fall out of this:

1. **File-based result capture is the one capture contract.** Promote the editors' write-to-file-then-poll into fragments (`client-file-output` + `artifact-transform`). This replaces the summary's mangled stdout-tail and the supervisor's stdout/`AGENT_DONE` split with one adapter-neutral, corruption-proof channel. *(This supersedes the earlier "structured JSON output" idea — file-based is engine-agnostic and already proven.)*
2. **drain-dag: convert the board-I/O surface, keep the loop body raw.** It should compose `comms-post` (status), a new `task-dag-post` (queue ops), and optional `catalog-pull` (context_refs) — but **not** `completion-report`/`scout-choreography`/`feedback-protocol`, which assume a one-shot stage agent, not a polling loop.

---

## 4. Missing fragments (the new building blocks)

| Fragment | Purpose | Priority | Consumers |
|---|---|---|---|
| **client-file-output** | Standard write+poll contract: file naming (`.summary`/`.analysis`/`.split.draft`), poll-ready triggers, uniform error reporting | **P0** | editor Analyze/Split, artifact Summary |
| **artifact-transform** | Pure read→derive→write contract: read source, validate output, write derived file, never mutate original / re-read own output | **P0** | Split, Analyze, Summarize, future artifact-mutation flows |
| **board-start-context** | Pull-once-at-start board context (governance + tasks + recent + catalog) as a preamble; distinct from on-demand `catalog-pull` | **P1** | Decompose, board-run, any FSM-aware skill |
| **task-dag-post** | Declarative task/sub-tree post `{task, parent_id, depends, executor, description}` → `/comms/tasks` | **P1** | drain-dag, Decompose planner, `planning/consolidate` |
| **context-limit-contract** | Shared bounding schema (max-items, truncation, empty-section handling) for all context reads | P2 | `comms_context.py`, `hydrate.py` |
| **agent-output-redirect** | Optional scratchpad for non-artifact reasoning, gated on a flag | P3 | `development/debug`, `planning/po` |

---

## 5. Proposed phasing (strawman — architect to refine)

- **P0 — client composition seam.** Make `cliEngine`/`aiRouter` request a composed skill from the manifest (expose `compose_skill` to the renderer via an FSM endpoint or a TS mirror). Add `client-file-output` + `artifact-transform`. Convert Summary + Analyze + Split to: composed prompt → file output → poll. *Fixes the codex/claude summary-quality bug as a side effect.*
- **P1 — board connection for client actions.** Add `board-start-context`; inject it into Summary/Decompose. Convert Goal Decompose (planner) to compose `planning/plan`. Add `task-dag-post`; convert drain-dag's board-I/O surface.
- **P2 — consolidation.** Unify result capture on the file channel across server + client. `context-limit-contract`.
- **P3 — polish.** `agent-output-redirect`; convert remaining raw board skills (`team/architect`, `team/research`).

---

## 6. Open questions for the roles

**PO (scope):**
- Which actions are *pure transforms* (no board side-effects — Analyze/Split/Summary) vs *board agents* (Decompose/Execute)? The transform set composes `client-file-output`+`artifact-transform` but NOT `comms-post`; is that right, or should every transform also post an `artifact` to the board so its output is discoverable?
- Is the editor (markdown) surface in scope, or only the Command-Center board actions?

**Architect (technical):**
- Where does client-side composition live — an FSM HTTP endpoint that returns the composed prompt, or a TypeScript mirror of `compose_skill`? (DB-overridable manifest argues for server-side.)
- Does the loop executor (`_run_loop` frontier) route through composition, or stay supervisor-Python-only?
- Exact contract for `task-dag-post` and `board-start-context` (payload shapes, skip-if-down).

**Designer (UX consistency):**
- One feedback language: today we have board posts (server), milestone toasts (editor), and a status badge+toast (summary). Pick one model, or define when each applies.
- How does a *client* action's progress surface — a board `status` post (like server agents), a toast, or both? Should client actions open a visible terminal tab (like board runs now do)?

---

## 7. What this fixes along the way

- **Summary quality** (codex chrome / claude flattening) — solved by file-based capture, no per-engine parsing.
- **drain-dag duplication** — board I/O stops being per-adapter copy-paste.
- **Decompose** — gains board context + standard posting instead of a hard-coded Python POST.
- **One mental model** — "every CLI action composes fragments" replaces four bespoke call-sites.
