---

---
# Retro — stepper-pathly-ui

_Date: 2026-05-31 | Stage: RETRO | Model: claude-sonnet-4-6_

---

## What went well

**1. Cross-repo architecture held together cleanly.**
The separation of `playwright-stepper-framework` (CDP launcher, POMs, glue) from `pathly-adapters/studio` (data-testid additions) was the right call. Conversations 1 and 2 ran independently with zero file conflict, and the three-layer POM → Glue → Workflow JSON pattern was immediately recognizable as the existing openlibrary/saucedemo pattern. Future contributors won't need to learn a new structure.

**2. CDP-over-connect is the correct Electron strategy.**
Python Playwright has no native `electron.launch()` API; the CDP path (`playwright.chromium.connect_over_cdp`) is the only portable option. The decision to make `electron_launcher.py` fully generic (no Pathly imports) paid off — constants pass in via arguments, making the launcher reusable for any future Electron app by changing only `electron_config.py`.

**3. data-testid naming convention established from scratch and stuck.**
The `{component}-{element}-{variant}` all-lowercase-kebab convention was agreed in the PO notes and followed consistently across all three screens. No drift between Conv 2 (addition) and Conv 3 (POM locators). The tester confirmed zero CSS/ID selectors in any POM file.

**4. Builder surfaced a genuine spec gap mid-conversation rather than guessing.**
When Conv 2 discovered that `topbar-panel-plan`, `topbar-panel-editor`, and `topbar-panel-settings` had no corresponding DOM buttons, the builder filed an IMPL_QUESTIONS file instead of inventing buttons or silently omitting the testids. This kept the spec honest and led to a correct scope adjustment (sidebar BottomNav testids for settings/monitor, plan/editor out of scope).

---

## What went wrong

**1. Three test failures required a fix conversation.**
The tester found three legitimate failures:
- AC1.4: `--browser electron --cdp-port` CLI args were parsed but never forwarded to `run()` and `launch_browser()`. The programmatic API worked; the CLI path did not.
- AC3.3: `TopBarPage` was missing the `sidebar-nav-monitor` locator despite `BottomNav.tsx` having the testid.
- AC5.4: `pathly_settings.json` took a screenshot of settings but never programmatically read or asserted the routing engine value — exactly what the criterion required.

All three were genuine correctness gaps, not ambiguous criteria. They could have been caught with a pre-commit self-check by the builder (import the POM and confirm all locators, run the workflow schema validator, diff the CLI arg-forwarding chain).

**2. Reviewer caught 9 violations — all button/style rule violations in Studio files.**
The Conv 2 builder added testids correctly but did not audit the files for pre-existing `studio/CLAUDE.md` rule violations (no inline styles, `type="button"` on every button). The reviewer caught V1–V7 across `topbar/index.tsx`, `PanelNav.tsx`, `HomeScreen.tsx`, and `IconButton.tsx`. These were pre-existing problems the builder touched files for, but the CLAUDE.md rules make the builder responsible for leaving files at least as clean as found. V8 (POM validation mismatch with `"python-fsm"`) and V9 (StepperSession not calling `register_all_sites`) were genuine implementation gaps.

**3. The plan's smoke workflow structure in IMPLEMENTATION_PLAN was later contradicted by the scope adjustment.**
`IMPLEMENTATION_PLAN.md` Conversation 5 section included `pathly_navigate_panel` steps for `"plan"` and `"editor"` panels — but the scope adjustment from Conv 2 (IMPL_QUESTIONS) had already established those panels are not navigable via topbar buttons. The plan was not updated after the scope adjustment, so the builder inherited contradictory instructions and produced a smoke workflow that first included plan/editor steps (reverted in review).

---

## What to do differently next time

**1. CLI arg-forwarding must be an explicit verify step in every conversation that adds CLI arguments.**
Any conversation that adds `argparse` arguments must have a done-condition that includes: run the CLI with the new argument and confirm it reaches the intended code path (not just that `--help` shows the flag). Add to `CONVERSATION_PROMPTS.md` pattern: `"Verify: python stepper/main.py --browser electron --cdp-port 9222 --workflow <file> 2>&1 | grep -i cdp"`.

**2. Studio file touches must include a studio/CLAUDE.md rules audit.**
Any conversation that modifies a Studio component file must end with an explicit step: "Read studio/CLAUDE.md and confirm all `<button>` elements in touched files have `type=` attributes, and no new inline styles were introduced." Add this as a mandatory checklist item in the `CONVERSATION_PROMPTS.md` template for Studio-touching conversations.

**3. Scope adjustments from mid-conversation questions must propagate back to the plan immediately.**
When a builder files an IMPL_QUESTIONS feedback file and the orchestrator resolves it, the resolution must also update any downstream conversation prompts in `CONVERSATION_PROMPTS.md` that reference the now-out-of-scope items. The Conv 5 smoke workflow contradictions arose because the IMPL_QUESTIONS resolution changed the testid/navigation model but Conv 5's prompt still referenced `"plan"` and `"editor"` panel navigation.

**4. POM locator completeness should have a grep-based done-condition.**
Conv 3's done-condition should include: `grep -n "sidebar-nav-" poms/pathly/pages/top_bar_page.py` — expected: at least two matches (settings and monitor). A single-line grep would have caught the missing `sidebar-nav-monitor` locator before the tester found it.

---

## Metrics

| Metric | Value |
|---|---|
| Conversations planned | 5 |
| Conversations executed | 5 |
| Review cycles | 2 (initial review: 9 violations; second: PASS) |
| Test failures found | 3 |
| Fix conversations needed | 1 |
| Stories: PASS | S1, S2, S3, S4, S5, S6 — all 6 |
| Total builder agent spawns | 4 (Conv 2, 3, 4, 5) |
| Total tokens (all agents) | ~278,691 |
| Total cost | ~$1.50 |
