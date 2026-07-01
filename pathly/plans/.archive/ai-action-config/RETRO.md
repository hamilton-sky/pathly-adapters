# RETRO — ai-action-config

## What shipped
A single shared configurator (`PromptActionConfig`) reused across the editor's **Split**, **Analyze**, and **Comments** surfaces — preset/action dropdown + Prompt banner + EXTRA INSTRUCTIONS + engine picker, matching the board **Configure Evaluator** look. The comment card gained the full config; the comments-panel header gained a defaults popover; both comment send paths became engine-selectable (`buildCliArgv`, no hardcoded `'claude'`). The board **Evaluate** surface was left untouched as the reference design.

## What went well
- The shared primitives (`CliSelect`, `BoardSelect`, `PromptBanner`) already existed, so most of this was composition, not new building.
- Tokenizing the Split/Analyze default prompts to `{{FILE}}` + `resolvePrompt` kept default behavior byte-identical while enabling presets.
- Posting decisions + artifacts to the comms board gave the user live visibility into each stage.

## Lessons (promote to process)
1. **Check working-tree state vs HEAD before assuming scope.** A prior session had already refactored Evaluate onto the shared component as *uncommitted* changes not shown in the initial git snapshot. "Don't refactor Evaluate" actually meant "Evaluate already has the component — reuse it elsewhere." Always `git status` + diff vs HEAD before acting on a refactor directive.
2. **Sequence builders when files overlap.** Conv 2 and Conv 3 both touched `editorCli.ts` and `commentUtils.ts`; running them sequentially avoided clobbering.
3. **Know the FSM gate markers.** `VERIFY.md` must have `RESULT: PASS` as **line 1**; `PLANNING→DESIGNING` requires the literal `## Conversation` substring in `IMPLEMENTATION_PLAN.md`; `DESIGNING→BUILDING` requires `## Design System Output` in `DESIGN.md`.
4. **Interactive team flow does NOT auto-mirror to the comms board.** Board posts need an explicit `/comms/post` with the `X-Pathly-Secret` header (`~/.pathly/server_secret.txt`). Runner mode mirrors automatically; interactive mode does not.
5. **Portal popovers out of `overflow:hidden` panels.** The comment-defaults popover clipped until it was portaled to `document.body` and fixed-positioned — same idiom as `EvalConfigPopover`. Prefer extending the shared component with additive optional props (`showBanner`/`showFooter`) over forking it.

## Follow-ups (not blocking)
- Manual UI pass of the new comment-card config after reload (functional + typecheck verified).
- Optional: persist comment-card EXTRA per-comment vs. session (currently per-open).
- Nothing committed yet — changes are in the working tree for the user to review (per standing policy: no auto-commit/push).
