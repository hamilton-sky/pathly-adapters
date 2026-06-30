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
2. **Cost + tokens + tool calls (BUILT)** — the first cut forced buffered `--output-format json`,
   which froze the editor's stdout-driven progress (reverted). The shipped path is a **stream-json
   renderer**: one-shots run `--output-format stream-json --verbose`; the pure `claudeJson.ts`
   module (called from `terminal.ts`) turns the event stream back into clean prose + live "⚙ Tool"
   lines (streaming + milestone toasts preserved, raw JSON never shown) and reads `total_cost_usd`
   / `usage` / tool-count from the final `result` event → POSTed to `/db/invocation` (tool count
   lands in the otel span attributes, answering "where do I see tool calls"). Robust to PTY
   line-wrapping, multi-chunk events, and non-JSON noise — and because the renderer is the one
   piece that can't be checked against live claude here, it's covered by synthetic-event unit
   tests (`claudeJson.test.ts`).

## Why this design

- **Aggregate-on-read** holds: each one-shot is one append-only fact row tagged by tier; no
  stored counters. (See `telemetry-three-tier`.)
- **terminal.ts does the heavy lifting** → consumers change ~2 lines (pass meta + opt into json).
- Editor actions read their result from a **file** (`pollForFile`/`fs.read`), so the JSON
  envelope switch does not affect their output; aiRouter reads stdout, handled by tail-normalization.

## Status / limits

- claude one-shots: full **cost + tokens + tool-count + streaming** via the stream-json renderer.
- **codex** one-shots: span-only (time/tier/label/adapter) — no claude-style result event to parse;
  revisit if codex gains a stream-json mode. The renderer only activates for `stream-json` tabs, so
  codex keeps raw passthrough.
- Needs verification in the running app: the renderer is unit-tested against synthetic events, but
  the live claude stream-json event shapes/flags should be confirmed once (run an AI Analyze → the
  terminal should stream clean prose + "⚙ Tool" lines, and DB Explorer should show cost+tokens).
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
