# Add Operator mode and confirmation cards to the HQ picker

Type: task
Status: resolved
Blocked by: 03
Test first: no

Studio (TSX) work, after the loop exists:

- The HQ model picker gains an **Operator (local)** mode next to the
  model cards: selecting it routes HQ messages to `llm:operate`
  instead of `llm:chat`. The mode is explicit and visible (badge in
  the panel header while active) — never a silent upgrade of the
  read-only copilot.
- `operator:confirm` renders a confirmation card inline in the chat:
  the plain-text description, the exact tool + args (collapsible),
  **Run** / **Cancel** buttons → answers via `operator:resolve`.
  Cards show the money-relevant facts (what spawns, on what) because
  spawns bill cloud agents.
- While a confirmation is pending, the input is disabled with a
  "waiting for your decision" state (no interleaved messages
  racing the gate).
- Match the panel's current visual language; extend the HQ components,
  don't fork them.

## Not in this ticket

- The loop itself: ticket 03. Audit display: ticket 05 (log first,
  surface later if wanted).

## Done when

- `pnpm --filter studio typecheck` exits 0 and the HQ-related vitest
  suite passes.
- Manual: Studio dev, Operator mode, "pause the builder" → card
  appears with exact args → Run executes (visible in board), Cancel
  does nothing; input locks while a card is pending.

```check
$ pnpm --filter studio typecheck
exit 0
```

## Reference

- spec.md § UI, § Happy path; ticket 03's IPC event shapes
- HQ panel + ModelSelector components (read-only)

## Answer

Superseded 2026-10-14 by the composer design the user approved (handoff
"Decided"): no "Operator (local)" mode in the model picker. Zero actions
ticked = the read-only copilot; one or more = the operator. Built instead:

- Composer chip row (`HQ/ComposerScope/`): `[⚡ Actions n/8 ▾]` opens the
  shared popover's **Actions** tab (`ActionsTab/` + `useActionSelection`):
  catalog actions Settings allows, grouped by domain, risk in words,
  presets, cap 8 with `aria-disabled` + reason (never auto-untick), polite
  "N of 8 enabled". Ticks: `store/hqActionsStore.ts` (`pathly-hq-actions`).
- **Settings → Intelligence → HQ actions** (`Settings/HqActionsSettings/`):
  which catalog actions HQ may use at all.
- Confirm cards (`HQ/ActionCards/`): verb + target, risk, Run / Cancel;
  Run never auto-focused, no Enter binding; cards run in order; each ends
  as a one-line record. The "input locked while a card is pending" idea is
  dropped: proposals don't block the model turn, so there is no race to
  guard, and the user can keep asking while a card waits.
- The visible "operator on" signal is the Actions chip count and the
  answer's context line "· N actions".

Tests: `ActionsTab.test.tsx`, `ActionCard.test.tsx`, `ComposerScope.test.tsx`.
Manual check: see ticket 06.
