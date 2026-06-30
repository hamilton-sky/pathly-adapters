# Telemetry — Universal Spans (every CLI the app spawns is observable)

## Goal

Close the telemetry blind spot left by `telemetry-three-tier`: **renderer-driven CLI
one-shots** (editor AI actions, HQ-chat summaries) spawn client-side via `terminal:spawn`
and never touched the Python supervisor, so they wrote **no** `agent_invocation` / `otel_span`
and never appeared in DB Explorer or the Σ roll-up. Only supervisor-driven runs (FSM/team,
board/single/loop) were observable.

After this feature: **every CLI the app spawns is one observable, tier-tagged span.**

## Tiering (per user direction)

- Editor / chat one-shots → **project** tier (ambient, not bound to a feature board).
- Feature board / goal runs → **feature** tier (already covered by the supervisor projector).
- Global = sum of all tiers (aggregate-on-read, unchanged).

## Mechanism

`terminal.ts` (the Electron main-process spawn gate) is the **single chokepoint** every CLI
spawn already passes through. It is now the universal *client-side* projector — the analog of
`supervisor/terminal.py::_emit_executor_telemetry` for renderer spawns.

- New optional `meta.telemetry = { scopeTier, label, feature?, role? }` arg on `terminal:spawn`.
- On exit of a **gated headless one-shot that is not a runner tab** and carries telemetry meta,
  `terminal.ts` parses the JSON result (cost/tokens) and POSTs `/db/invocation`.
- One writer, two callers: the new `POST /db/invocation` endpoint wraps the existing
  `runner/telemetry.py::project_agent_done`, so client one-shots and supervisor runs converge
  on the **same** schema and the same Σ roll-up. Each one-shot mints its own standalone trace.

### Output format follows the PROGRESS SOURCE (design rule)

The output format must match where a spawn draws its live progress — get this wrong and you
either lose cost or freeze the UI:

- **Board / goal / FSM runs** draw progress from the **board** (EVENTS.jsonl events written by
  fragments). The terminal is secondary → `--output-format json` is fine (cost reads from stdout).
- **Editor / chat one-shots** draw progress from the **terminal stdout stream** (`attachProgress`
  → milestone toasts + the live pill). They **must stream** → plain `--print`. Buffered json
  freezes that stream. The format legitimately differs by spawn type for this reason.

### Two parts

1. **Universal spans** — wall-time, tier, label, adapter, exit. Zero risk; 100% coverage now
   (cost/tokens null for one-shots until part 2). **DONE.**
2. **Cost + tokens (DEFERRED — must not regress UX)** — the first cut forced
   `--output-format json` on the one-shots; that buffered the stream and broke the editor's live
   progress, so it was reverted. The correct path is a **stream-json renderer in `terminal.ts`**:
   run one-shots with `--output-format stream-json`, re-emit assistant text deltas as clean prose
   (streaming + toasts preserved), surface `tool_use` events as live "⚙ Tool" lines, and read
   `total_cost_usd` / `usage` / tool-count from the final `result` event. Cost + tokens + tool
   calls, no UX cost.

## Why this design

- **Aggregate-on-read** holds: each one-shot is one append-only fact row tagged by tier; no
  stored counters. (See `telemetry-three-tier`.)
- **terminal.ts does the heavy lifting** → consumers change ~2 lines (pass meta + opt into json).
- Editor actions read their result from a **file** (`pollForFile`/`fs.read`), so the JSON
  envelope switch does not affect their output; aiRouter reads stdout, handled by tail-normalization.

## Status / limits

- One-shots are currently **span-only** (time / tier / label / adapter); streaming UX is intact.
  Cost/tokens arrive when the stream-json renderer (part 2) is built.
- **codex** one-shots: span-only regardless (no claude-style result event); revisit if codex gains
  a stream-json mode.
- The diagram action (`useEditorDiagramAction.ts`) landed via the parallel md-diagram commit
  (848032ad) carrying its telemetry meta; this feature supplies the `terminal:spawn` meta-arg infra
  it depends on.

## Files

- Python: `runner/telemetry.py` (+`adapter` attr), `ops/db_api_invocation.py` (new `POST /db/invocation`),
  `ops/db_api.py` (register), `tests/test_telemetry_three_tier.py` (+T6).
- Studio: `services/cliEngine.ts` (`jsonResult`), `EditorHeader/editorCli.ts`, `ipc/terminal.ts`
  (projector + tail-normalize), `preload/index.ts` + `types/global.d.ts` (spawn meta), consumers
  (`aiRouter.ts`, `useEditorAgentActions.ts`, `CommentsPanel.tsx`, `Editor/index.tsx`,
  `useEditorDiagramAction.ts`), `aiRouter.test.ts`.
