# Walkthrough & Interactive-Graph Panel — graph-fed, board-native

> Proposal artifact. Extends the Board Differ with a **narrative walkthrough** and an
> **interactive-graph sidecar panel**, both fed by the code graph Pathly already owns.
> Sibling to the MVP (surfaces a–d in [APPROACH.md](../APPROACH.md)); does not replace it.

## The idea in one line

The three downloaded skills (`code-review-visual`, `change-walkthrough`, `code-tour`) are
**interactive-HTML-graph generators** — parameterized by scope, they emit a self-contained page
with pan/zoom/drag graphs (import subgraph, model diagram, flow/sequence). We **keep their
presentation shell and swap their engine**: their structure comes from a Python-AST parser
(TS-shallow); ours comes from `/code/query` (language-agnostic). One brain, many surfaces.

## Content vs presentation — the split that makes it trustworthy

| Layer | Who produces it | Why |
|---|---|---|
| **Structure** (nodes, edges, callers, affected flows) | the **graph** via `/code/query` | deterministic, language-agnostic, no hallucinated edges |
| **Narrative** (intent, themes, per-file "what & why", risk) | the **agent** | prose the graph can't produce |
| **The interactive graph itself** (SVG pan/zoom/drag) | a **renderer**, from the two above | consistent per run, safe to render, drawn once |

The agent **never draws the graph** and **never hand-writes HTML** — it emits a small JSON
(mirroring the markdown editor's `.diagrams.json` append contract: *agent owns the write,
renderer only reads*). This is the single most important correction to "spawn one agent that
produces the HTML": the agent produces **data**, the renderer produces the **picture**.

## Honest engine note (verified on this board)

The architect consultation (msg `ea509df0`) established that **`detect_changes` is whole-repo
working-tree-vs-HEAD and takes no target/diff**, and `op:impact` currently aliases `op:callers`.
That is a constraint on the *live impact panel* — but it **favors this proposal**: the
walkthrough agent queries **`/code/query op:callers|impact` on specific changed files**, which
already works today (verified live: `impact` on a file returns real per-symbol caller/callee
counts). We consume the **built** per-file query, not the unbuilt whole-repo `detect_changes`.
Label impact honestly ("callers of the changed symbols", not "hypothetical per-hunk impact").

## The interactive-graph sidecar panel

You already ship the exact pattern: the markdown editor's **`DiagramGalleryPanel`** reads a
`.diagrams.json` sidecar and renders each entry as a card in a right-docked gallery. The differ's
graph panel is that pattern applied beside the diff — a docked rail holding **N interactive
graphs**, each an entry:

| Graph | Source | Interaction |
|---|---|---|
| **Import / dependency subgraph** of the changed files | `/code/query` graph edges | drag-pan, scroll-zoom, drag-node, dbl-click reset |
| **Impact graph** — changed symbol → affected callers/flows | `op:callers`/`impact` per file | same |
| **Model diagram** — domain classes + fields | AST of the changed files (fields never drift) | drag/zoom |
| **Flow / sequence** — the execution path through the change | agent narrative | zoom/pan |

Same append-array contract, same gallery mechanics, same on-open hydrate chip — a
`WalkthroughGalleryPanel` / `GraphGalleryPanel` mirrors `DiagramGalleryPanel` almost 1:1.

## One contract, surfaced many ways

| Surface | Renderer | For |
|---|---|---|
| Inline in the Command Center | native React (themed via `tokens.css`, interactive, deep-linked) | reviewing a run in-app |
| Sidecar graph panel | the graph gallery above | inspecting structure/impact beside the diff |
| Exported `.html` board artifact | thin renderer (reuse the `change-walkthrough` HTML shell) | sharing / archiving outside the app |

**Modes, not separate skills:** `walkthrough` (git diff → orient) · `review` (diff → severity) ·
`tour` (dir/glob, no diff → onboarding) are a `mode` + `scope` parameter on **one** skill + **one**
JSON contract. Not three engines, not a renderer per mode.

## Two ways to draw the interactive graph (pick per effort)

1. **HTML-in-webview** — reuse the downloaded generator's HTML output directly, shown in a webview
   tab. Fastest reuse; the tradeoff is Electron webview + theme mismatch.
2. **React-native SVG** *(recommended)* — the gallery panel draws the graphs from the JSON with a
   small pan/zoom hook. Board-native, themed, no webview; reuses `DiagramGalleryPanel` wiring.

## Rollout (relative to the MVP)

1–4. MVP surfaces (a)–(c) + Impact panel, and (d) multi-file run review — unchanged.
5. **Walkthrough JSON one-shot** — single agent, `/code/query`-fed, emits the sidecar JSON.
6. **Graph gallery panel** — renders the JSON's graphs beside the diff (React-native).
7. **HTML export** — same JSON → shareable `.html` board artifact. Fast-follow, not a blocker.

## Open questions

- Baseline for the diff the walkthrough narrates: run-start commit vs `HEAD` (same open question
  as the MVP — capture the run-start SHA now regardless).
- Graph freshness: force a reindex on the changed files before the one-shot, or label the graph
  advisory (it can lag recent edits).
- Is the graph panel a **new** docked rail in the differ, or a tab inside the existing Impact
  panel? (designer call — keep it subordinate to the diff, per the DESIGNER consultation.)
