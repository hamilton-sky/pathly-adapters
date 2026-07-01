# USER_STORIES — ai-action-config

## Story 1 — Shared configurator powers Evaluate (no behavior change)
**As** a Studio user configuring a board evaluation,
**I want** the Evaluate popover to look and behave exactly as it does today,
**so that** the refactor onto a shared component is invisible to me.

**Acceptance criteria**
- [ ] The Evaluate popover renders the same sections in the same order: LENS dropdown, prompt banner, EXTRA INSTRUCTIONS, ENGINE, the "Run on this board" note, and Reset / Run now.
- [ ] The default "Propose tasks" lens still shows the read-only skill-backed banner with "Open in Markdown Editor"; named lenses still show the editable prompt banner.
- [ ] Selecting a lens, editing the lens prompt, typing extra instructions, choosing an engine, Reset, and Run now all work as before; ⌘/Ctrl+Enter still runs.
- [ ] The popover still closes on outside-click / Escape and lens-dropdown clicks do not close it.
- [ ] `tsc --noEmit -p studio/tsconfig.web.json` is clean.

## Story 2 — Split offers refactor presets
**As** a user restructuring a markdown/skill file,
**I want** a dropdown of refactor presets (plus my own editable prompt) in the Split config,
**so that** I can pick how the file is refactored instead of editing one prompt by hand.

**Acceptance criteria**
- [ ] The Split prompt config shows a preset dropdown with at least: Restructure into sections (default), Split into finer cells, Tighten prose, Normalize headings.
- [ ] The default preset's prompt is byte-identical to today's `buildSplitPrompt` output for the open file (Unicode punctuation preserved).
- [ ] Editing the prompt, "Use once", and "Save default" still work; the per-action engine (`CLI_KEY_SPLIT`) still persists independently.
- [ ] A previously saved Split override is preserved on upgrade (loaded as edits to the default preset, not lost).
- [ ] Running Split writes to `<file>.draft` exactly as before.

## Story 3 — Analyze offers analysis lenses
**As** a user reviewing a file,
**I want** a dropdown of analysis lenses in the Analyze config,
**so that** I can analyze through different perspectives (quality, clarity, gaps, redundancy) without rewriting the prompt.

**Acceptance criteria**
- [ ] The Analyze prompt config shows a preset dropdown with at least: Full quality review (default), Clarity & ambiguity, Completeness / gaps, Redundancy & token cost.
- [ ] The default preset's prompt is byte-identical to today's `buildAnalyzePrompt` output for the open file.
- [ ] Use once / Save default / per-action engine (`CLI_KEY_ANALYZE`) all behave as before; existing override preserved on upgrade.
- [ ] Running Analyze writes to `<file>.analysis` exactly as before.

## Story 4 — Comments let me pick the engine
**As** a user sending a comment / comments to an AI,
**I want** to choose the CLI engine,
**so that** I'm not locked to Claude.

**Acceptance criteria**
- [ ] The comment card shows a compact engine selector; the primary button reads **"Send to {engine}"** (e.g. "Send to Claude", "Send to Codex") and reflects the selection.
- [ ] The CommentsPanel header has a config trigger that opens the shared configurator to set the panel's default engine + preset; the footer button reads **"Send to {engine}"**.
- [ ] The chosen engine is used to spawn (both the single-comment "send now" path and the panel "Send to Agent" path call `buildCliArgv(cli, …)`, not a hardcoded `'claude'`).
- [ ] The default engine persists under `CLI_KEY_COMMENT` across reloads.
- [ ] With the default engine = Claude and default preset, the produced prompt and `<file>.draft` flow are identical to today (no regression).

## Story 5 — Comment presets are action templates
**As** a user adding a comment,
**I want** to choose what the AI should do with my selection (Apply change / Explain / Find / Ask),
**so that** the comment is framed for the right action.

**Acceptance criteria**
- [ ] Comment presets come from a single shared verb list also referenced by `SelectionTooltip` (no duplicated verb definitions).
- [ ] The default preset reproduces today's "address each reviewer comment" behavior.
- [ ] Selecting a non-default preset reframes the send prompt accordingly.

## Cross-cutting acceptance criteria (all stories)
- [ ] All four surfaces use the same `PromptActionConfig` component and the same `CliSelect` engine dropdown.
- [ ] Evaluate remains the only surface whose preset list contains a `skillRef`-backed preset.
- [ ] No inline `style={{…}}` except the documented exceptions; all theming via tokens / CSS modules.
- [ ] Every component file stays within the ~150-line guide (one job per file).
- [ ] Renderer and main-process typechecks are clean.
