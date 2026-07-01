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
| **a** | **Artifact vs git HEAD** (read-only) | artifact card → "See changes" | `CodeDiffView` (read-only split/unified) | Low — reuses existing viewer | **1st** |
| **b** | **Agent draft vs original** (accept/reject hunks) | a board run stages a `.draft` | full `DraftDiffViewer` triage + apply | Higher — reconstruct/apply path | 2nd |
| **c** | **Two artifact messages** (side-by-side) | user picks any two board artifacts | `DraftDiffViewer`, source pair = two files | Medium | 3rd |

All three are the **same `DraftDiffViewer` component** with a different *source
pair* — exactly the "all progressively" instinct, reordered so the highest-value
/ lowest-cost piece ships first.

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

## Architecture — reuse everything already built

```
 Artifact card (board)              Studio (renderer, TS)
        │  "See changes"                    │
        ▼                                    ▼
  window.pathly.fs.read(artifact) +   DraftDiffViewer (source pair)
  git show HEAD:<path>                 ├─ CodeDiffView  (the diff)
        │                              └─ ImpactPanel   (NEW)
        ▼                                    │
  POST /code/query { op:"impact", target:<file>, role:"reviewer" }
        ▼
  Pathly code/ gateway ─► codebase-memory-mcp cli detect_changes '{...}'
        ◄──────────────── { changed_symbols, affected_flows, callers }
```

### Backend (small, additive — reuses the `code/` blueprint + CliProvider)
- **`code/query.py`** — accept `op:"impact"` and route it to a new
  `CliProvider.detect_changes(target)` that runs `codebase-memory-mcp cli
  detect_changes '{"repo_path": <root>, ...}'` and returns the affected-symbols
  JSON. Reuses the existing cache, role gate, board logging, and never-500. (~20
  lines; same shape as the graph query.)
- No FSM / DB / new transport — one more `op` on an endpoint agents already use.

### Frontend (Studio)
- **Artifact card** gains a "See changes" action → opens `DraftDiffViewer` with
  `{ originalPath: <git HEAD blob>, draftPath: <artifact file> }` in read-only
  mode (surface a).
- **`ImpactPanel/`** (new, own folder + CSS module per Studio rules) — calls the
  `/code/query op:"impact"` route for the diffed file(s) and renders the affected
  callers / flows; a hunk can show a `⚠ N callers` badge.
- Reuses the existing `useDraftDiff` / `CodeDiffView`; surfaces (b)/(c) add the
  triage/apply and second-file-picker paths already present in the component.

### Main process
- One IPC helper (`git show HEAD:<path>` for the baseline blob), or reuse an
  existing git bridge if present.

---

## Rollout order

1. **Surface (a)** read-only artifact-vs-HEAD from the artifact card (reuses
   `CodeDiffView`) — smallest, most general.
2. **Impact panel** — `code/query op:"impact"` backend + `ImpactPanel` frontend
   (the differentiated feature; depends only on surface a's diff being present).
3. **Surface (b)** draft-triage (accept/reject) when board runs stage `.draft`s.
4. **Surface (c)** two-artifact compare (power feature).

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
