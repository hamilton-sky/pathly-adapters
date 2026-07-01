# CONVERSATION_PROMPTS — ai-action-config

Builder runs these in sequence. Each is a self-contained build unit. Architecture and contracts are in `IMPLEMENTATION_PLAN.md` and `STORM_SEED.md`. After each conversation run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` from the repo root and fix until clean.

Repo root: `C:/Users/Yafit/pathly-adapters`. All paths under `studio/src/renderer/src/`.

> **Scope guard:** **Do NOT modify the board Evaluate surface** (`EvalConfigPopover.tsx`, `agentFormData.ts`). Evaluate is the *reference* design and stays exactly as-is — the evaluator prompt is a separate board-only feature. We build a shared configurator modeled on Evaluate's body and use it ONLY in Split, Analyze, and Comments.

---

## CONV 1 — Build shared `PromptActionConfig` (standalone)

**Goal:** Create a reusable, presentational configurator component modeled on the board Evaluate popover body (`EvalConfigPopover`), so Split / Analyze / Comments can all share one interaction model. **Do not touch Evaluate** — read it only as the reference.

**Read (reference, do not edit):**
- `components/CommandCenter/CommsPanel/GoalsView/EvalConfigPopover.tsx` + `EvalConfigPopover.module.css` — the visual/interaction template to mirror.
- `components/shared/BoardSelect/BoardSelect` (preset dropdown), `components/MarkdownEditor/EditorHeader/CliSelect/CliSelect` (engine dropdown; `EditorCli` type from `../editorCli`), `components/shared/PromptPreview/PromptPreview` (`PromptBanner`).

**Create**
- `components/shared/PromptActionConfig/presetTypes.ts`
  ```ts
  export interface PromptPreset { name: string; label: string; hint: string; prompt: string; skillRef?: string }
  export function resolvePrompt(template: string, vars: Record<string, string>): string
  // replace every {{KEY}} with vars[KEY]; leave unknown tokens untouched
  ```
- `components/shared/PromptActionConfig/PromptActionConfig.tsx` — presentational; **import ONLY** `CliSelect`, `BoardSelect`, `PromptBanner` (no zustand, no skill-catalog, no md-editor). Props:
  ```ts
  interface Props {
    heading: string
    presetLabel?: string            // section label above the dropdown; default 'PRESET'
    presets: PromptPreset[]
    selectedPreset: string
    promptText: string
    extra: string
    cli: EditorCli
    running?: boolean
    primaryLabel: string
    onSelectPreset: (name: string) => void
    onPromptTextChange: (v: string) => void
    onExtraChange: (v: string) => void
    onCliChange: (cli: EditorCli) => void
    onReset: () => void
    onPrimary: () => void
    bannerSlot?: React.ReactNode    // optional; replaces the default editable PromptBanner
    footerNote?: React.ReactNode
    secondaryLabel?: string
    onSecondary?: () => void
    showExtra?: boolean             // default true
  }
  ```
  Render order: heading → preset `BoardSelect` (leading `Sparkles`, options from presets) → (`bannerSlot` ?? editable `PromptBanner` on `promptText`/`onPromptTextChange`) → extra `<textarea>` when `showExtra !== false` → `CliSelect` under "ENGINE" → optional `footerNote` → footer (Reset · optional secondary · primary). ⌘/Ctrl+Enter → `onPrimary`. < 150 lines (extract a `ConfigFooter` if needed).
- `components/shared/PromptActionConfig/PromptActionConfig.module.css` — **port** section/sectionLabel/optional/textarea/footer/resetBtn/primary/spacer/redirect rules from `EvalConfigPopover.module.css` (token-only, responsive). Do NOT copy the `.popover` portal/positioning shell — callers own their own shell.

**Acceptance:** component compiles and is self-contained; `tsc --noEmit -p studio/tsconfig.web.json` clean; **Evaluate untouched**; no other surface wired yet.

---

## CONV 2 — Split & Analyze adopt the shared configurator

**Goal:** Re-host the editor's Split and Analyze prompt configs on `PromptActionConfig`, adding a preset dropdown, preserving Use-once / Save-default / per-action engine and exact default-prompt bytes. **Do not touch Evaluate.**

**Create**
- `components/MarkdownEditor/EditorHeader/actionPresets.ts` — `SPLIT_PRESETS: PromptPreset[]` and `ANALYZE_LENSES: PromptPreset[]`.
  - Split default (`name:''`) `prompt` = current `buildSplitPrompt` output with the file path replaced by `{{FILE}}` (otherwise byte-identical; keep Unicode-preservation lines). Add: `cells` (finer per-topic cells), `tighten` (condense prose, no meaning loss), `headings` (normalize heading hierarchy).
  - Analyze default (`name:''`) `prompt` = current `buildAnalyzePrompt` output, path → `{{FILE}}`. Add: `clarity` (ambiguity/misread risks), `gaps` (completeness/missing edge cases), `redundancy` (verbosity + token cost).
  - Reuse the existing default text from `Editor/commentUtils.ts` (tokenize it there and import) — do not hand-duplicate the prompt strings.

**Modify**
- `components/MarkdownEditor/EditorHeader/editorCli.ts` — add `PRESET_KEY_SPLIT`, `PRESET_KEY_ANALYZE` + `loadPreset(key)/savePreset(key,name)`.
- `components/MarkdownEditor/EditorHeader/PromptPeekModal/PromptPeekModal.tsx` — re-host on `PromptActionConfig`: add `presets`, `selectedPreset`, `onSelectPreset`; selecting a preset loads `resolvePrompt(preset.prompt, { FILE })` into the editable text; keep Reset (→ default preset), Use once (`onPrimary`), Save default (`onSecondary`), `CliSelect`. **Migration:** an existing legacy `STORAGE_KEY_SPLIT`/`_ANALYZE` override loads as the editable text of the default preset (never discarded).
- `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` — add `splitPreset`/`analyzePreset` name state (seed from `PRESET_KEY_*`), pass to the two `PromptPeekModal` usages, persist on change.
- `components/Editor/commentUtils.ts` — export the tokenized default Split/Analyze templates so `actionPresets.ts` reuses them; keep `getEffectivePrompt`/run path (`useEditorAgentActions`) working — the resolved prompt is what reaches `buildCliArgv`.

**Acceptance:** Split/Analyze show a preset dropdown; default preset reproduces today's prompt exactly for the open file; Use once / Save default / engine persistence unchanged; legacy overrides preserved; run still writes `.draft`/`.analysis`; typecheck clean; **Evaluate untouched**.

---

## CONV 3 — Comments: engine selection + presets (card + panel)

**Goal:** Let users pick the CLI engine for comment sends (per-send in the card, default in the panel header) and frame the send with a preset verb. Remove the hardcoded `'claude'`. **Do not touch Evaluate.**

**Create**
- `components/Editor/commentVerbs.ts` — `COMMENT_VERBS: PromptPreset[]` (Apply change [default] / Explain / Find similar / Ask). `SelectionTooltip` and the comment configurator both import this (single source of truth).
- `components/Editor/CommentsPanel/CommentConfigButton/CommentConfigButton.tsx` (+ `.module.css`) — header trigger (Cpu/SlidersHorizontal) opening `PromptActionConfig` (presets = `COMMENT_VERBS`, default comment engine, `showExtra` optional) to set the panel default engine + preset.

**Modify**
- `components/MarkdownEditor/EditorHeader/editorCli.ts` — add `CLI_KEY_COMMENT = 'pathly.editor.cli.comment'` + `PRESET_KEY_COMMENT`.
- `components/Editor/CommentModal/CommentModal.tsx` — add a compact `CliSelect` next to the actions; rename the primary button to **`Send to {cliLabel(cli)}`**; change `onSendNow` to `(body, color, cli)`; default the card engine from `CLI_KEY_COMMENT`.
- `components/Editor/index.tsx` — `handleModalSendNow(body, color, cli)` uses `buildCliArgv(cli, prompt)` (not `buildHeadlessArgv('claude', …)`); frame `prompt` with the selected comment verb.
- `components/Editor/CommentsPanel/CommentsPanel.tsx` — add `CommentConfigButton` to the header; footer button → **`Send to {cliLabel(defaultCli)}`**; `handleSendToAgent` spawns with `buildCliArgv(defaultCli, …)`; persist default engine/preset.
- `components/Editor/SelectionTooltip/SelectionTooltip.tsx` — source its verb(s) from `commentVerbs.ts` (keep the existing `onComment` flow working; minimal change).
- `components/Editor/commentUtils.ts` — `buildSendPrompt` accepts the selected verb/preset to frame the instruction; default verb reproduces today's "address each reviewer comment" prompt byte-for-byte.

**Acceptance:** comment card shows an engine selector + "Send to {engine}"; panel header opens the shared configurator and its footer reads "Send to {engine}"; both send paths use the chosen engine via `buildCliArgv`; default (Claude + default verb) byte-identical to today; `CLI_KEY_COMMENT` persists; typecheck clean; **Evaluate untouched**.
