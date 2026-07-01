# STORM_SEED — ai-action-config

**Feature:** Unify the AI-action configurator (preset prompts + extra instructions + engine dropdown) across the four "send to an AI" surfaces in Studio, so they share one component and one interaction model — each surface keeping its own prompt presets.

## Problem

Four places let a user fire a one-shot AI run, but each grew its own UI:

| Surface | Component | Engine picker | Prompt config | Preset list |
|---|---|---|---|---|
| Board **Evaluate** | `EvalConfigPopover` | ✅ `CliSelect` | ✅ `PromptBanner` + extra-instructions | ✅ `EVAL_LENSES` |
| Editor **Split** | `PromptPeekModal` | ✅ `CliSelect` | ⚠️ one editable textarea | ❌ |
| Editor **Analyze** | `PromptPeekModal` | ✅ `CliSelect` | ⚠️ one editable textarea | ❌ |
| MD **Comments** | `CommentModal` / `CommentsPanel` | ❌ hardcoded `'claude'` | ❌ | ❌ |

The board's `EvalConfigPopover` is the most complete and is the target pattern. Split/Analyze already share `CliSelect` but lack a preset dropdown. Comments have neither an engine picker nor prompt config — both send paths call `buildHeadlessArgv('claude', …)` directly.

## Decision — extract one shared configurator, feed it per-surface presets

The board popover is built from three reusable primitives that already exist:
`CliSelect` (engine) · `BoardSelect` (preset dropdown) · `PromptBanner` (preview/edit).
Extract the popover **body** into a shared `PromptActionConfig` and have each surface supply its own preset list.

```
        ┌──────────────────────────────────────────────┐
        │  <PromptActionConfig>  (shared, layer-light)  │
        │  preset dropdown · prompt banner ·            │
        │  extra instructions · CliSelect · footer      │
        └──────────────────────────────────────────────┘
             ▲           ▲            ▲            ▲
        EVAL_LENSES  SPLIT_PRESETS ANALYZE_LENSES COMMENT_PRESETS
        (+ skillRef   (refactor      (analysis      (verbs from
         default)      styles)        lenses)        SelectionTooltip)
```

## Key technical decisions (resolved)

1. **New generic preset type — does NOT touch eval.** Define a fresh `PromptPreset { name; label; hint; prompt; skillRef? }` for the shared component and the three new surfaces. `EvalLens`/`EvalConfigPopover` stay exactly as they are. `skillRef` is reserved for future skill-backed presets; none of the three new surfaces set it. This keeps "the eval prompt is a separate board feature" (user point #5) literally true — Evaluate is the reference, not a refactor target.

2. **Path-parameterized prompts via a token, not a function.** Split/Analyze prompts embed the file path (`buildSplitPrompt`/`buildAnalyzePrompt`). To fit them into a static preset list, store each preset's `prompt` as a template containing a `{{FILE}}` token and resolve with `resolvePrompt(template, { FILE })` at run time. Eval lenses have no token → unchanged. The **default** Split/Analyze presets are the *current* prompt text verbatim (path → `{{FILE}}`), so existing behavior and the byte-preservation rules are preserved exactly.

3. **Layer-clean shared component.** `PromptActionConfig` must NOT import the skill catalog / md-editor navigation (those are eval-only). The default editable `PromptBanner` is rendered internally; eval passes an optional **`bannerSlot`** that replaces it with its read-only skill-backed banner. This keeps the shared file free of feature-specific deps and under the 150-line limit.

4. **Comments get the configurator in two places (user points #7 + #8):**
   - **Comment card** (`CommentModal`) — a compact engine pill next to the action button; **"Send to Claude" → "Send to {engine}"**; the per-send engine flows through `onSendNow(body, color, cli)`.
   - **CommentsPanel header** — a config trigger opening `PromptActionConfig` to set the panel's **default** engine + preset for the "Send to Agent" footer (footer label also becomes "Send to {engine}").
   New `CLI_KEY_COMMENT` persists the default engine. Both send paths swap the hardcoded `'claude'` for `buildCliArgv(commentCli, …)`.

5. **Comment presets = SelectionTooltip verbs.** A comment is selection-scoped, so its "presets" are action templates (Apply change · Explain · Find similar · Ask). Source them from one shared verb list so the tooltip and the comment configurator never drift. Default preset reproduces today's "apply each reviewer comment" behavior.

## Non-goals

- No backend/FSM changes — this is renderer-only.
- No change to *what* the engines do or how PTYs spawn (reuse `buildHeadlessArgv`/`buildCliArgv`).
- **Evaluate is not modified at all** — it is the reference design only. `EvalConfigPopover` keeps its own implementation; we do NOT re-host it on the shared component. The shared component is built standalone (mirroring eval's body) and used only by Split, Analyze, and Comments.
- User-editable preset CRUD is out of scope (presets are a fixed starter list, like `SYSTEM_PROMPTS` today).

## Risks / watch-items

- **Prompt-override migration:** Split/Analyze currently persist a single override under `STORAGE_KEY_SPLIT`/`STORAGE_KEY_ANALYZE`. With presets, persist (selected-preset-name + per-preset edits). Must not silently drop a user's saved prompt — treat an existing override as edits to the default preset on first load.
- **Byte-preservation:** the default Split/Analyze prompt text must survive the `{{FILE}}` tokenization unchanged (Unicode em-dash, curly quotes, ellipsis).
- **150-line / one-job rules:** `PromptActionConfig` stays presentational; surface wrappers own their state. Split if it grows.
