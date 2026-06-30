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

### Two parts

1. **Universal spans** — wall-time, tier, label, adapter, exit. Zero risk; 100% coverage
   immediately (cost/tokens may be null).
2. **Cost + tokens** — opt the one-shot argv into `claude --output-format json` (new
   `SpawnOpts.jsonResult`). `terminal.ts` already had `parseClaudeJsonResult`; it now reuses it
   for one-shots to read `total_cost_usd` + `usage`, and **normalizes the exit tail to the
   agent's `.result` prose** so stdout-reading consumers (aiRouter) stay clean.

## Why this design

- **Aggregate-on-read** holds: each one-shot is one append-only fact row tagged by tier; no
  stored counters. (See `telemetry-three-tier`.)
- **terminal.ts does the heavy lifting** → consumers change ~2 lines (pass meta + opt into json).
- Editor actions read their result from a **file** (`pollForFile`/`fs.read`), so the JSON
  envelope switch does not affect their output; aiRouter reads stdout, handled by tail-normalization.

## Known tradeoff / limits

- Under `--output-format json` the editor terminals show a buffered JSON result instead of live
  streaming, and `attachProgress` milestone toasts (stdout-driven) pause. The **elapsed pill
  survives** (it derives from `tab.startedAt`, not stdout). Restoring live streaming would need a
  stream-json renderer in `terminal.ts` — deferred.
- **codex** one-shots: no claude-style result to parse → **span-only** (cost/tokens 0). Acceptable;
  most one-shots default to claude.
- The diagram action (`useEditorDiagramAction.ts`) is part of the untracked md-diagram WIP; its
  telemetry meta rides in the working tree and lands when that feature commits.

## Files

- Python: `runner/telemetry.py` (+`adapter` attr), `ops/db_api_invocation.py` (new `POST /db/invocation`),
  `ops/db_api.py` (register), `tests/test_telemetry_three_tier.py` (+T6).
- Studio: `services/cliEngine.ts` (`jsonResult`), `EditorHeader/editorCli.ts`, `ipc/terminal.ts`
  (projector + tail-normalize), `preload/index.ts` + `types/global.d.ts` (spawn meta), consumers
  (`aiRouter.ts`, `useEditorAgentActions.ts`, `CommentsPanel.tsx`, `Editor/index.tsx`,
  `useEditorDiagramAction.ts`), `aiRouter.test.ts`.
