# Board Differ — impact-aware diff view on the Command Center

## Goal

Give the human supervisor a **board-native diff view**: from an artifact card on
the board, see *what an agent run changed* — and, because Pathly now has a code
graph, *what that change affects* (callers / execution flows). This turns the
board from "read the agent's summary" into "see and vet the actual change."

It is a **human-facing consumer of the same code-knowledge graph the agents use**
(codebase-memory-mcp). One brain, many surfaces: agents query it via B/C, the
differ enriches diffs via `detect_changes`. No second code-analysis engine.

---

## The three surfaces (progressive — ship in this order)

The evaluator proposed starting with the draft-triage flow (b); we **reorder to
start with (a)** — it is the most general, the cheapest (read-only), and the
natural home for the impact panel.

| # | Surface | Trigger | Component | Cost | Order |
|---|---|---|---|---|---|
| **a** | **Artifact vs git HEAD** (read-only) | artifact card → "See changes" | `RawCodeDiffView` (new ~45-LOC presenter over `SplitDiff`/`UnifiedDiff`) | Low — reuses primitives one level below `CodeDiffView` | **1st** |
| **b** | **Agent draft vs original** (accept/reject hunks) | a board run stages a `.draft` | full `DraftDiffViewer` triage + apply | Higher — reconstruct/apply path | 2nd |
| **c** | **Two artifact messages** (side-by-side) | user picks any two board artifacts | `DraftDiffViewer`, source pair = two files | Medium | 3rd |

**Decision (architect · 2026-07-15):** Do NOT reuse `useDraftDiff` or `CodeDiffView`
for surface (a). `useDraftDiff` diffs by `## ` markdown headings; `CodeDiffView`
assumes `DiffHunk[]` and rebuilds a markdown document. For code-file line diffs the
correct reuse seam is one layer down: `computeLineDiff` + `SplitDiff`/`UnifiedDiff` +
`toSplitRows`/`toUnifiedRows` from `Editor/DraftDiffViewer/` — wrapped in a new
`RawCodeDiffView` (~45 lines). Authoritative architecture: `ARCHITECTURE_PROPOSAL.md`.

**Cross-cutting for all three: the Impact panel** (see below) — the Pathly-
differentiated feature.

---

## The Impact panel (`detect_changes`) — why this is Pathly, not just a diff

`codebase-memory-mcp` ships `detect_changes`: *map git diff hunks → indexed
symbols → affected execution flows*. "Artifact vs HEAD" (surface a) **is** a git
diff, so it feeds `detect_changes` directly. Rendered beside the diff:

```
build_block changed  →  3 callers affected: get_provider, code_query, build_prompt
                        affects flow: runner prompt assembly
```

The review question shifts from *"do these lines look right?"* to *"accepting
this touches these 3 callers — intended?"* — the rigor story the board exists for.

---

## The Walkthrough artifact — single-agent, graph-fed (the shareable fidelity)

Surfaces (a)–(c) are *inline* diff viewers. A run may also want a **narrative artifact** —
"what this run did, why, and what it touches" — read top-to-bottom and shareable outside the
app. That is the `change-walkthrough` / `code-review-visual` family, **rebuilt on the engine
Pathly already owns** (`detect_changes` / `/code/query`) instead of their Python-AST core — so
it works on Studio's own TypeScript, not just the Python orchestrator.

**One skill, single agent, reusing machinery we already ship** — the markdown editor's
Analyze/Diagram one-shots (CLI agent → JSON sidecar → a gallery panel that only reads). No new
spawn path.

**Content vs presentation — the split that makes it trustworthy:**
- **Structure comes from the graph, not the LLM.** The prompt calls `/code/query`
  (`op:"impact"`/`"callers"`) for the changed files and hands the agent the REAL caller/callee
  edges + affected flows. The agent never draws the import graph itself (that is the
  hallucination the deterministic Python engine avoided) — and the graph is language-agnostic,
  which is what closes the "Python-deep, TS-shallow" gap.
- **Narrative comes from the agent** — intent, theme clustering, per-file "what changed & why",
  risk temperature.
- **The agent emits JSON, not hand-written HTML** (mirrors the `.diagrams.json` append
  contract: agent owns the write, renderer only reads). Cheaper, consistent per run, safe to
  render.

**One contract, surfaced many ways** (board-differ's own "one brain, many surfaces"):

| Surface | Renderer | For |
|---|---|---|
| Inline in the Command Center | native React (themed via `tokens.css`, interactive, deep-linked) | reviewing a run in-app — reuses `CodeDiffView` + `ImpactPanel` |
| Exported `.html` board artifact | thin renderer (reuse the `change-walkthrough` HTML shell, engine swapped to consume the graph JSON) | sharing / archiving a run outside the app |
| Board attachment | `/comms/attach` → deep-links from the run message | making the walkthrough a first-class board citizen |

**Modes, not separate skills.** `walkthrough` (git diff → orient) · `review` (diff → severity
findings) · `tour` (dir/glob, no diff → onboarding) are a `mode` + `scope` parameter on the ONE
skill + ONE JSON contract — not three engines, not a renderer per mode.

---

## Architecture — reuse everything already built

> **Superseded in detail by `ARCHITECTURE_PROPOSAL.md` (2026-07-15).** The summary
> below is kept for orientation; use the proposal for implementation decisions.

```
 Artifact card (board)              Studio (renderer, TS)
        │  "See changes"                    │
        ▼                                    ▼
  window.pathly.fs.read(artifact) +   CodeDiffModal
  git show HEAD:<path>  (via IPC)      ├─ RawCodeDiffView (new — SplitDiff/UnifiedDiff)
        │                              └─ ImpactPanel (new, collapsible)
        ▼                                    │
  POST /code/query { op:"impact", target:<file>, role:"reviewer" }
        ▼
  Pathly code/ gateway ─► codebase-memory-mcp cli detect_changes '{...}'
        ◄──────────────── { changed_symbols, affected_flows, callers }
```

### Backend (small, additive — reuses the `code/` blueprint + CliProvider)
- **`code/query.py`** — new `op:"impact"` branch → `CliProvider.detect_changes(project_root)`
  shells `codebase-memory-mcp cli detect_changes`, filters result to the target file, returns
  the callers/symbols block or `null` (never-500 contract unchanged). Helper functions
  `_is_code_file` / `_filter_to_target` go in `blueprints/code/_helpers.py` to keep
  `query.py` under the 400-line SRP limit. (~60–100 LOC total.)
- No FSM / DB / new transport — one more `op` on an endpoint agents already use.

### Frontend (Studio)
- **Artifact card** gains a "See changes" pill — visible only when `artifactPath` is set
  and is a code file — that opens `CodeDiffModal`.
- **`CodeDiffModal`** (new) — combines `RawCodeDiffView` (diff) with collapsible
  `ImpactPanel`. NOT `DraftDiffViewer` (that is surface (b), accept/reject).
- **`RawCodeDiffView`** (new, ~45 LOC) — takes two raw strings → `computeLineDiff` →
  `SplitDiff`/`UnifiedDiff`. Reuses primitives from `Editor/DraftDiffViewer/` one level
  below `CodeDiffView`; does NOT call `buildDocument`. See `ARCHITECTURE_PROPOSAL.md §2`.
- **`ImpactPanel`** (new) — queries `/code/query op:"impact"`, renders callers/flows, hides
  on `null` (graceful degradation when graph is off or file has no impact).
- **`useCodeFileDiff`** (new hook) — baseline from `git.showFile` IPC + current from
  `fs.read`; returns `{original, draft}` as raw strings (no diff logic in the hook).

### Main process
- **`ipc/git.ts`** — new `git:show-file` handler (`git show HEAD:<rel>`, null on untracked),
  exposed as `window.pathly.git.showFile` via preload + `global.d.ts`.

---

## Rollout order

1. **Surface (a)** read-only artifact-vs-HEAD from the artifact card (reuses
   `CodeDiffView`) — smallest, most general.
2. **Impact panel** — `code/query op:"impact"` backend + `ImpactPanel` frontend
   (the differentiated feature; depends only on surface a's diff being present).
3. **Surface (b)** draft-triage (accept/reject) when board runs stage `.draft`s.
4. **Surface (c)** two-artifact compare (power feature).
5. **Walkthrough artifact (native)** — the single-agent `walkthrough` skill: prompt pulls
   `/code/query` impact facts → JSON sidecar → rendered natively in the Command Center. The
   narrative layer over the impact panel; reuses the Analyze/Diagram one-shot + gallery pattern.
6. **Walkthrough export (HTML)** — the same JSON → self-contained `.html` board artifact for
   sharing (reuses the `change-walkthrough` HTML shell). Fast-follow, not a blocker.

---

## Relationship to the code-intelligence initiative

Depends on `code-intel-backend-decision` (codebase-memory-mcp) being active —
the differ's Impact panel is a *second consumer* of that graph. Gated the same
way: no graph / backend off → the differ still shows the plain text diff, the
Impact panel is simply absent (graceful degradation, mirrors the agent side).

## Open questions
- Does `detect_changes` read the working-tree diff itself, or take a diff/paths
  argument? (verify the tool contract before wiring the backend op.)
- Baseline for surface (a): last **committed** HEAD vs last **run-start** commit?
  Default to committed HEAD; revisit if runs span multiple commits.
- Non-code artifacts (markdown plans): show the text diff only (no Impact panel);
  the panel is code-file-only.
