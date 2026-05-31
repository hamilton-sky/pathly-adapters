# REVIEW_FAILURES — stepper-pathly-ui

Reviewer: reviewer (claude-sonnet-4-6)
Date: 2026-05-31
Rigor: lite
Scope: Conv 1–5 cross-repo review (playwright-stepper-framework + pathly-adapters/studio)

---

## Status: BLOCKED

9 violations found. No changes may be merged until all are resolved.

---

## Violations

### V1 — studio/topbar/index.tsx:46 — Button rule — `topbar-back-btn` missing `type="button"`

**File:** `studio/src/renderer/src/components/topbar/index.tsx:46`
**Rule:** studio/CLAUDE.md — every `<button>` must have an explicit `type` attribute
**Detail:** The "Projects" back-navigation button renders without `type="button"`. In a form context this defaults to `type="submit"` and may trigger unexpected form submission.

---

### V2 — studio/topbar/PanelNav.tsx:14,31 — Button rule — panel nav buttons missing `type="button"`

**File:** `studio/src/renderer/src/components/topbar/PanelNav.tsx:14` and `31`
**Rule:** studio/CLAUDE.md — every `<button>` must have an explicit `type` attribute
**Detail:** Both `topbar-panel-flow` and `topbar-panel-monitor` buttons have no `type` attribute.

---

### V3 — studio/HomeScreen.tsx — No-inline-styles rule — entire component styled with `style={{ }}` props

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Rule:** studio/CLAUDE.md — no inline styles; all styling goes in the component's `.module.css` file
**Detail:** `HomeScreen`, `FsmBadge`, `FlowTypeBadge`, `renderSectionLabel`, `renderCard`, and all layout containers use exclusively `style={{ }}` JSX props. No `HomeScreen.module.css` exists. The only accepted exceptions (dynamic progress bar via `<progress>`, imperative `ref.current.style.setProperty` in `useEffect`) do not cover general layout, color, spacing, or animation styles. This is a wholesale violation of the rule, not an edge case.

---

### V4 — studio/HomeScreen.tsx — Button rule — multiple `<button>` elements missing `type="button"`

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Rule:** studio/CLAUDE.md — every `<button>` must have an explicit `type` attribute
**Affected elements (approximate lines):**
- Pin/star button (~344)
- Remove project button (~369)
- `homescreen-open-btn` (~467)
- Tab buttons in header loop (~538)
- "Go to Projects" button (~673)
- `homescreen-new-project-btn` (~733)
- `homescreen-view-grid-btn` (~757)
- `homescreen-view-list-btn` (~773)
- `home-toggle-done-btn` (~790)
- `home-show-more-btn` (~877)

None of these carry `type="button"`.

---

### V5 — studio/HomeScreen.tsx:44,52 — No-inline-styles rule — SVG helper components use `style={{ display: 'block' }}`

**File:** `studio/src/renderer/src/components/HomeScreen.tsx:44` (`IconArrow`), `52` (`IconClose`)
**Rule:** studio/CLAUDE.md — no inline styles
**Detail:** Both inline SVG helper components pass `style={{ display: 'block' }}` directly on the `<svg>` element. This is not exempt under the accepted exceptions.

---

### V6 — studio/ui/IconButton.tsx — No-inline-styles rule — full visual state computed and applied as inline style

**File:** `studio/src/renderer/src/components/ui/IconButton.tsx:32-65`
**Rule:** studio/CLAUDE.md — no inline styles
**Detail:** `IconButton` computes its complete visual state (dimensions, background, border, color, cursor, opacity, flexShrink, transition, padding) as a `baseStyle` object and passes it as `style={baseStyle}` to the underlying `<button>`. The static portions belong in a CSS module; dynamic hover/disabled states should use CSS custom properties or class toggling.

---

### V7 — studio/ui/IconButton.tsx:52 — Button rule — `<button>` missing `type="button"`

**File:** `studio/src/renderer/src/components/ui/IconButton.tsx:52`
**Rule:** studio/CLAUDE.md — every `<button>` must have an explicit `type` attribute
**Detail:** The `<button>` rendered inside `IconButton` has no `type` attribute. Because `IconButton` is used extensively throughout the TopBar (sidebar toggle, chat toggle, theme toggle, copy-window button), this violation propagates to all usages.

---

### V8 — poms/pathly/pages/settings_page.py:41 — Correctness — `set_routing_engine` validation list does not match caller convention

**File:** `C:\Users\Yafit\playwright-stepper-framework\poms\pathly\pages\settings_page.py:41`
**Rule:** Correctness — POM validation must match the values callers are expected to pass
**Detail:** `set_routing_engine` accepts `engine in ["llm", "python"]` and raises `ValueError` otherwise. However:
- The Studio store uses `routingEngine === 'python-fsm'` as the canonical string for the Python FSM option.
- The `settings_action.py` docstring documents `{ "action": "pathly_set_routing", "extra": { "engine": "llm" } }` but also shows the internal testid is `settings-routing-python`.
- If any caller (workflow JSON or test) passes `"python-fsm"` (the UI-native value), the POM raises `ValueError` and the action returns `status="failed"`.

The allowed values `["llm", "python"]` are inconsistent. Either the POM must accept `"python-fsm"` or the documentation/testid must be aligned to `"python"` throughout.

---

### V9 — engine/runner/api.py:100–111 — Correctness — `StepperSession` does not register Pathly glue actions

**File:** `C:\Users\Yafit\playwright-stepper-framework\stepper\engine\runner\api.py:100-111`
**Rule:** Correctness — actions used in Pathly workflows must be available in the registry
**Detail:** `StepperSession.__aenter__` manually registers only OpenLibrary, SauceDemo, and phpTravels page modules. It does not call `register_all_sites(...)`. A caller using `StepperSession` to run `pathly_smoke.json` or `pathly_settings.json` will receive `ActionNotFound` errors for all seven Pathly actions (`pathly_open_project`, `pathly_new_project`, `pathly_assert_projects`, `pathly_set_routing`, `pathly_save_settings`, `pathly_navigate_panel`, `pathly_toggle_chat`). The CLI path (`main.py`) does call `register_all_sites` correctly; the programmatic API does not.

---

## Warnings (non-blocking)

- `stepper/engine/browser/electron_launcher.py:34` — Resource leak — the `pw` (`async_playwright`) instance is never stopped on the success path. The caller receives only `browser.contexts[0]` and has no handle to stop Playwright. Consider returning a tuple `(context, pw)` or accepting a pre-started `pw` instance.
- `stepper/sites/pathly/workflows/pathly_smoke.json` — Structural inconsistency — the smoke workflow treats "settings" as a third panel but navigates to it via `sidebar-nav-settings` (sidebar BottomNav), while flow and monitor are navigated via `topbar-panel-*` buttons. This works correctly at runtime but the abstraction is inconsistent.
- `poms/pathly/__init__.py` — Eager imports — all three page classes are imported unconditionally at module level. An import error in any one will break the entire `poms.pathly` namespace.

---

## What passed

- Electron launcher retry timing (500ms interval), `ElectronLaunchError` on timeout, returns `browser.contexts[0]` — correct.
- `electron_config.py` constants-only module — no layer violation.
- `infra.py` `launch_browser()` extension — correct dispatch pattern.
- `main.py` `--browser`/`--cdp-port` args — correct.
- `test_electron_launcher.py` — both success and timeout paths verified; `pw.stop()` asserted.
- All three POMs (`HomeScreenPage`, `SettingsPage`, `TopBarPage`) — `BasePage` subclass, `[data-testid="..."]`-only selectors, correct `open()` no-op docstring, no stepper-layer imports.
- Glue actions (`home_screen_action.py`, `settings_action.py`, `top_bar_action.py`) — correct `GlueAction`/`PageModule` subclass pattern, `step.extra` access, `StepResult` return, `ValueError` caught and returned as `failed`.
- `register.py` — all 7 action names registered correctly.
- `pathly_settings.json` — valid JSON, correct action name.
- `Settings/index.tsx` — CSS module used, `type="button"` on save button, ARIA on FSM input — clean.
- `BottomNav.tsx` — `type="button"` on both buttons, testids present — clean.
- `test_pathly_glue.py` — both passing and failing code paths exercised.
