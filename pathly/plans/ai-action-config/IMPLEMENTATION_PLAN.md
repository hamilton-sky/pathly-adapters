# IMPLEMENTATION_PLAN — ai-action-config

Renderer-only refactor (`studio/src/renderer/src/`). Three build conversations, each typecheck-clean and independently shippable.

## Architecture

### New shared component — `components/shared/PromptActionConfig/`
Presentational, layer-light (no skill-catalog / md-editor imports). Composes existing primitives.

**`presetTypes.ts`**
```ts
export interface PromptPreset {
  name: string          // stable id; '' = first/default row
  label: string         // dropdown label
  hint: string          // dropdown sub-text
  prompt: string        // inline template; may contain {{FILE}} (and other) tokens
  skillRef?: string     // set ONLY for skill-backed presets (eval default) → caller renders a read-only banner
}
export function resolvePrompt(template: string, vars: Record<string, string>): string
// replaces {{KEY}} with vars[KEY]; leaves unknown tokens untouched
```

**`PromptActionConfig.tsx`** — the shared popover body. Props:
```ts
interface Props {
  heading: string
  presets: PromptPreset[]
  selectedPreset: string
  promptText: string                 // editable text of the active inline preset
  extra: string
  cli: EditorCli
  running?: boolean
  primaryLabel: string               // 'Run now' | 'Use once' | 'Send to {engine}'
  onSelectPreset: (name: string) => void
  onPromptTextChange: (v: string) => void
  onExtraChange: (v: string) => void
  onCliChange: (cli: EditorCli) => void
  onReset: () => void
  onPrimary: () => void
  bannerSlot?: React.ReactNode       // when set, replaces the default editable PromptBanner (eval skill banner)
  footerNote?: React.ReactNode       // eval's "Need an agent? Run on this board"
  secondaryLabel?: string            // optional 2nd action (editor 'Save default')
  onSecondary?: () => void
  showExtra?: boolean                // default true; comment card may hide it to stay compact
}
```
Renders: `heading` → preset `BoardSelect` → (`bannerSlot` ?? editable `PromptBanner`) → (extra textarea) → `CliSelect` → `footerNote` → footer (Reset · secondary · primary). ⌘/Ctrl+Enter triggers `onPrimary`. Stays < 150 lines; extract a `ConfigFooter` sub-component if needed.

### Per-surface preset data
- **Eval** — **untouched.** `EvalConfigPopover` stays exactly as-is; it is the *reference* design the shared component mirrors (modeled-on, not refactored-into). The evaluator prompt remains a separate board-only feature.
- **Editor** — new `MarkdownEditor/EditorHeader/actionPresets.ts`: `SPLIT_PRESETS` + `ANALYZE_LENSES`. The default of each = current `buildSplitPrompt`/`buildAnalyzePrompt` text with the path replaced by `{{FILE}}`.
- **Comments** — new `Editor/commentVerbs.ts`: a single `COMMENT_VERBS` list (Apply / Explain / Find / Ask) consumed by BOTH `commentPresets` and `SelectionTooltip`.

### Surface wiring (each owns its own state; shared component is stateless)
| Surface | Wrapper / owner | State added |
|---|---|---|
| Eval | **untouched — reference only** | — |
| Split/Analyze | `EditorHeader.tsx` + `PromptPeekModal.tsx` (re-hosted on `PromptActionConfig`) | `splitPreset`/`analyzePreset` name; reuse `splitCli`/`analyzeCli` |
| Comment card | `CommentModal.tsx` + `Editor/index.tsx` | per-send `cli` (seed from `CLI_KEY_COMMENT`); `onSendNow(body,color,cli)` |
| Comment panel | `CommentsPanel.tsx` | header config popover; default `cli` + preset; footer uses `buildCliArgv` |

### Storage keys (`editorCli.ts`)
Add `CLI_KEY_COMMENT = 'pathly.editor.cli.comment'`. Add preset-name keys: `PRESET_KEY_SPLIT`, `PRESET_KEY_ANALYZE`, `PRESET_KEY_COMMENT` (selected preset name). Keep existing `STORAGE_KEY_SPLIT`/`STORAGE_KEY_ANALYZE` override semantics → loaded as edits to the default preset (migration-safe).

## File map

**New**
- `components/shared/PromptActionConfig/PromptActionConfig.tsx`
- `components/shared/PromptActionConfig/PromptActionConfig.module.css`
- `components/shared/PromptActionConfig/presetTypes.ts`
- `components/MarkdownEditor/EditorHeader/actionPresets.ts`
- `components/Editor/commentVerbs.ts`
- `components/Editor/CommentsPanel/CommentConfigButton/CommentConfigButton.tsx` (+ `.module.css`) — panel-header config trigger

**Untouched (reference only)**
- `components/CommandCenter/CommsPanel/GoalsView/EvalConfigPopover.tsx` + `agentFormData.ts` — the board Evaluate surface is the design reference and is NOT modified.

**Modified**
- `components/MarkdownEditor/EditorHeader/PromptPeekModal/PromptPeekModal.tsx` — host `PromptActionConfig` (preset dropdown)
- `components/MarkdownEditor/EditorHeader/EditorHeader.tsx` — preset state for split/analyze
- `components/MarkdownEditor/EditorHeader/editorCli.ts` — `CLI_KEY_COMMENT` + preset keys
- `components/Editor/CommentModal/CommentModal.tsx` — engine pill + "Send to {engine}"
- `components/Editor/CommentsPanel/CommentsPanel.tsx` — header config + footer label + `buildCliArgv`
- `components/Editor/index.tsx` — thread comment cli through `handleModalSendNow`
- `components/Editor/SelectionTooltip/SelectionTooltip.tsx` — source verbs from `commentVerbs.ts`
- `components/Editor/commentUtils.ts` — `resolvePrompt` use / preset-aware send prompt

## SOLID / CLAUDE compliance
- One job per file; shared component presentational, wrappers own state.
- No upward layer imports; shared component imports only `CliSelect`, `BoardSelect`, `PromptBanner`.
- No inline styles; CSS modules + tokens; responsive (min-width:0, no fixed widths).
- Every `<button type="button">`; ARIA on dropdowns/triggers.

## Conversation breakdown

Full per-conversation builder prompts live in `CONVERSATION_PROMPTS.md`. Summary:

- **## Conversation 1 — Shared `PromptActionConfig` (standalone).** Create the shared presentational component + `presetTypes.ts` (`PromptPreset`, `resolvePrompt`), modeled on Evaluate's body. **Evaluate is NOT modified.** Foundation — lands first.
- **## Conversation 2 — Split & Analyze preset dropdowns.** Add `actionPresets.ts` (`SPLIT_PRESETS`, `ANALYZE_LENSES`); re-host `PromptPeekModal` on the shared component; preserve Use-once / Save-default / per-action engine; migrate legacy overrides.
- **## Conversation 3 — Comments engine + presets.** `CLI_KEY_COMMENT`; comment card engine pill + "Send to {engine}"; CommentsPanel header config + footer label; `commentVerbs.ts` shared with `SelectionTooltip`; swap hardcoded `'claude'` for `buildCliArgv`.

## Sequencing
Conv 1 (foundation) → Conv 2 (split/analyze presets) → Conv 3 (comments engine+presets). Each gated by a clean `npm run typecheck`. Conv 1 must land first (defines `PromptActionConfig`); 2 and 3 depend on it but not on each other. **Evaluate is never modified — reference only.**
