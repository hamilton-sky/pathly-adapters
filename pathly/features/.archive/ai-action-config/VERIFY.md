RESULT: PASS

# VERIFY — ai-action-config (BUILD)

## What was built
Shared AI-action configurator reused across Split, Analyze, and Comments (Evaluate kept as reference, per user).

- **Conv 1** — `components/shared/PromptActionConfig/` (`PromptActionConfig.tsx`, `ConfigFooter.tsx`, `presetTypes.ts`, `.module.css`). Pre-existing in the working tree; verified. Evaluate consumes it (unchanged, kept per user decision).
- **Conv 2** — Split & Analyze re-hosted on `PromptActionConfig` with preset dropdowns (`actionPresets.ts`: `SPLIT_PRESETS`, `ANALYZE_LENSES`). Default prompts tokenized to `{{FILE}}` and resolved via `resolvePrompt` → byte-identical to the old `buildSplitPrompt`/`buildAnalyzePrompt`. Use-once / Save-default / per-action engine + legacy-override migration preserved (`PromptPeekModal.tsx`, `EditorHeader.tsx`, `editorCli.ts`, `commentUtils.ts`).
- **Conv 3** — Comments engine selection + verb presets. Card (`CommentModal.tsx`) gains a compact `CliSelect`; button reads **"Send to {engine}"**; `onSendNow(body,color,cli)`. Panel header (`CommentConfigButton/`) opens `PromptActionConfig` for the panel default engine + verb; footer reads **"Send to {engine}"**. Both send paths now use `buildCliArgv(cli, …)` instead of hardcoded `'claude'`. Verbs sourced from shared `commentVerbs.ts` (also used by `SelectionTooltip`). `CLI_KEY_COMMENT`/`PRESET_KEY_COMMENT` persist defaults.

## Checks
- **Renderer typecheck:** `tsc --noEmit -p studio/tsconfig.web.json` → **clean (exit 0)**.
- **Main-process typecheck:** `tsc --noEmit -p studio/tsconfig.node.json` → **clean (exit 0)**.
- **Scope:** changes limited to the files declared in `CONVERSATION_PROMPTS.md`. The board Evaluate surface (`EvalConfigPopover.*`, `agentFormData.ts`) and `shared/PromptActionConfig/*` were NOT modified by Conv 2/3 (eval diffs are the pre-existing Conv-1 working-tree state the user chose to keep).
- **Byte-identity:** default Split/Analyze prompts and the default comment send (engine=claude, default verb) produce byte-identical prompts/argv to pre-change behavior (`buildCliArgv('claude',p) === buildHeadlessArgv('claude',p)`).
- **Rules:** no inline styles; tokens-only CSS modules; `type="button"`; components within size guide; presentational shared component (props-driven).

## Manual UI verification
Not run in this headless pipeline pass — deferred to TEST stage (live preview of the four surfaces). Static gates (typecheck both configs, scope, byte-identity) all pass.
