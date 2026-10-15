# Show the context manifest in the HQ panel

Type: task
Status: resolved
Blocked by: 02, 03
Test first: no

Studio (TSX) work, after the API shape is stable. Under each HQ answer,
add a collapsible "context" line backed by `GET /hq/context`:

- Sections pulled (name + included/cut), tokens used of budget
  (`tokens_est / budget` with a small bar, mirroring the chief preview
  manifest pattern), and the `eligible_model` warning when false.
- The `[board context unavailable]` marker (ticket 03) renders as a
  visible amber note, never hidden.
- The manifest is read-only display; it sends nothing and changes no
  state.

Follow the existing HQ panel component structure (find the component
that renders HQ answers and the `/pathly` chips; extend it, don't fork
it). Match the panel's current visual language — no new design system.

## Not in this ticket

- Changing which models the picker offers: ticket 05 only reports
  eligibility.
- Any new server behavior: the endpoint already exists (ticket 03).

## Done when

- `pnpm --filter studio typecheck` (or the repo's documented Studio
  typecheck command) exits 0 and the HQ-related vitest suite passes.
- Manual: open Studio dev (`localhost:5173`), ask HQ "what needs my
  attention?" on a board with a pending question; the manifest expands
  showing the sections pulled and token usage; with board context forced
  unavailable the amber note appears.

```check
$ pnpm --filter studio typecheck
exit 0
```

## Reference

- spec.md § UI; ticket 03's `GET /hq/context` shape
- `studio/src/renderer/src/components/` HQ panel (read-only)

## Answer

Implemented 2026-10-14 (Studio TSX; extends the HQ panel, no fork).

- `store/chatStore.ts`: `Message` gains optional `contextManifest:
  HqContextManifest` (`tokens_est`, `budget`, `sections[]`, `model`,
  `eligible_model`, `unavailable`). Backward compatible.
- New `components/HQ/ContextManifest/`: `ContextManifest.tsx`
  (collapsible `context · 1.2k/6.0k tokens` line; expands to a token
  bar + per-section included/cut rows + model line; `eligible_model
  === false` shows an inline warning on the collapsed line),
  `ContextManifest.module.css` (panel's own visual language —
  `--text-muted`, `--accent`, and the `--yellow` amber note mirroring
  the panel's `toolBar`), `manifestUtils.ts` (pure helpers) +
  `manifestUtils.test.ts` (7 vitest tests, green).
- `MessageList.tsx` renders the manifest under assistant messages
  that carry one. The `[board context unavailable]` marker renders
  as the visible amber note (stripped from the answer text; no
  double-note when the manifest itself is unavailable).
- `useHQ.tsx`: `finishAssistantStream` (now async, awaited at both
  local-model call sites before `setLoading(false)` — no race)
  fetches `GET /hq/context?board=<activeTopic>&model=<selectedModelId>`
  via `apiFetch` and attaches the manifest with `updateLastMessage`.
  No board open → skipped; any fetch failure → the amber
  `unavailable` note. Read-only: the manifest sends nothing and
  changes no state.
- The prompt pipeline itself is untouched (per the ticket): the model
  still gets the client-side Conductor prompt; the manifest is the
  visibility/debugging surface.

Verification 2026-10-14: all touched files parse clean (esbuild);
the new vitest file passes 7/7; `pnpm typecheck` (run from
`studio/` — the repo has no pnpm-workspace.yaml, so `--filter
studio` matches nothing) exits 0 on the Mac. Environment note:
pnpm v11's `ERR_PNPM_IGNORED_BUILDS` gate blocked the install;
`pnpm approve-builds` wrote a new `studio/pnpm-workspace.yaml`
with `allowBuilds` for electron/esbuild/node-llama-cpp/node-pty/
protobufjs/sharp (first run denied everything — had to flip to
`true`). **Still pending**: the manual Studio check (open dev at
`localhost:5173`, ask HQ "what needs my attention?", expand the
context line; force board context unavailable, confirm the amber
note). Run it before marking resolved.

### Review follow-up 2026-10-14 — the prompt pipeline is wired

"The prompt pipeline itself is untouched" meant the feature did not work
end to end: the model answered from the Conductor prompt while the
manifest (fetched AFTER the answer) described a packet it never saw.

- `useHQ.handleSend` → `HQ/hqCopilot.ts::fetchHqTurn` → `POST /hq/prompt`
  BEFORE the model call; the returned system prompt + turn go to the model,
  the manifest is attached before streaming, a redirect is shown without
  calling the model. `shouldUseHqCopilot` keeps confident skill requests
  on the skill flow. The post-hoc `attachContextManifest` is gone.
- `context_tokens` reaches the runtime: Ollama `num_ctx` (unset, Ollama
  truncated the START of the prompt — the pending-questions section) and
  node-llama-cpp `createContext({contextSize: {min}})`; HQ answers get
  `maxTokens` 1024 (thinking models spend part of it).
- `qwen3-8b` (the settled default) added to the picker (`data/models.ts`);
  it was registered in main but not selectable.
- `ContextManifest.tsx`: `\u00b7`/`\u26a0` in JSX text rendered literally —
  now real characters; the inline-width bar is a `<progress>` (studio
  no-inline-style rule); aria-expanded uses the documented spread.
- `useHQ.tsx` had grown 874 → 923 past its frozen size; the stream helpers
  moved to `HQ/useAssistantStream.ts` → 863.

Studio: both typechecks exit 0; full vitest 22 files / 148 tests green
(new `hqCopilot.test.ts`, `usagePercent` cases). Still pending: the
manual check, which needs a downloaded model (none on this Mac yet).

### In-app check 2026-10-14 — resolved

Seen working in the real app (the user's Studio, Qwen3 8B built-in): Deep
reasoning streams into "Reasoning ▾"; the context line shows the board name
and token use; answers render as Markdown; the per-section choice works
(since moved from the answer's checkboxes to the composer's Context tab —
the line keeps a read-only record and an "Adjust for next question" link).
Fast measured headlessly at 2.4 s vs 18.5 s Deep on the same board
question. Found in the user's screenshot and fixed: with no board section
open, `resolveHqBoard` fell back to an `activeTopic` holding a goal-run
slug (an 83-token empty packet) — the fallback now must name a known
feature board; and the caret sat alone above a long context line.
