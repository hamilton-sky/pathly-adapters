# REVIEW — ai-action-config

Review was driven interactively (human-in-the-loop) plus static verification.

## Findings & resolutions
1. **Comment-defaults popover clipped (blocking, user-reported).** `CommentConfigButton`'s popover was `position:absolute` inside the comments panel (`overflow:hidden`) and clipped at the panel edge. **Fixed:** portaled to `document.body`, `position:fixed`, right-aligned (opens leftward), 290px — matches the Configure Evaluator popover.
2. **Configurators inconsistent with Evaluate (user request).** Split, Analyze, and the comment-defaults config had `showExtra={false}` and varied sizing. **Fixed:** EXTRA INSTRUCTIONS textarea enabled everywhere; Split/Analyze card narrowed 480→300px; all three now read like Evaluate (preset → prompt → extra → engine).
3. **Comment card lacked full config (user request).** **Fixed:** embedded `PromptActionConfig` (ACTION dropdown + EXTRA INSTRUCTIONS + engine) into `CommentModal`, removing the duplicate engine pill; card keeps its swatches, comment body, and Send/Add buttons. `onSendNow` now carries `(body, color, cli, verbName, extra)`.
4. **Shared component made more flexible (additive).** `PromptActionConfig` gained optional `showBanner`/`showFooter` and now hides an empty heading. Default behavior for Evaluate/Split/Analyze unchanged; also fixes a latent empty-heading strip in the Split/Analyze modal.

## Static checks
- Renderer typecheck (`tsconfig.web.json`): **clean**.
- Main-process typecheck (`tsconfig.node.json`): **clean**.
- **Scope:** board Evaluate surface (`EvalConfigPopover.*`, `agentFormData.ts`) untouched by this work (kept as the reference, per user). Changes confined to the shared component + editor Split/Analyze/Comments files.
- **Byte-identity:** default Split/Analyze prompts and the default comment send (Claude engine, default action, no extra) remain byte-identical to pre-change behavior; extra instructions append only when present.

## Outcome
PASS — all user-reported issues resolved; static gates green. Manual UI confirmation of the comment-defaults popover received ("looks good"); comment-card config pending the user's next reload.
