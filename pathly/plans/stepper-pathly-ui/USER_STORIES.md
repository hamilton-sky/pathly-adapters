# User Stories — stepper-pathly-ui

Source: PO_NOTES.md (authoritative). Stories are decomposed, not re-authored.

---

## S1 — Electron CDP launcher

**As** Yafit (Pathly Studio developer),
**I want** the Stepper framework to connect to a running Electron dev session over CDP,
**So that** I can drive the real Studio renderer — including `window.pathly.*` IPC — not a plain browser tab.

**Delivered by:** Conversation 1

### Acceptance criteria

- AC1.1: Calling `launch_electron_cdp(port=9222)` with Electron already running returns a Playwright `BrowserContext` without error.
- AC1.2: If the CDP port is not reachable, the launcher raises a clear error message naming the port and suggesting that Electron must be running with `--remote-debugging-port=9222`.
- AC1.3: The `StepperSession` class accepts an `electron_cdp_port` parameter; when supplied it uses `launch_electron_cdp` instead of `launch_browser`.
- AC1.4: The CLI (`stepper/main.py`) accepts `--browser electron --cdp-port 9222` and routes to the CDP launcher.
- AC1.5: A unit test covers `launch_electron_cdp` with a mocked CDP endpoint and asserts the returned context is the first context from the connected browser.
- AC1.6: A second Electron app can be wired in by changing only `electron_config.py` constants (executable path, default port) — not the launcher core in `electron_launcher.py`.

### Edge cases

- Port already in use by a different process: error message must distinguish "CDP not responding" from "port reachable but not Electron".
- Electron renderer not yet ready when `connect_over_cdp` is called: launcher must retry with a configurable timeout before failing (default from `electron_config.py`).

---

## S2 — data-testid attributes in Studio

**As** Yafit,
**I want** stable `data-testid` attributes on all interactive elements in HomeScreen, Settings, and TopBar,
**So that** Stepper POMs can target elements by test ID rather than brittle CSS selectors.

**Delivered by:** Conversation 2

### Naming convention (resolved)

`{component}-{element}-{variant}` — all lowercase kebab.
Examples: `homescreen-tab-projects`, `topbar-panel-flow`, `settings-routing-llm`.

### Acceptance criteria

- AC2.1: HomeScreen has testids: `homescreen-tab-projects`, `homescreen-tab-getting-started`, `homescreen-tab-settings`, `homescreen-new-project-btn`, `homescreen-project-card` (on each card), `homescreen-open-btn` (on each card's Open button), `homescreen-view-grid-btn`, `homescreen-view-list-btn`.
- AC2.2: Settings has testids: `settings-save-btn`, `settings-fsm-command-input`, `settings-routing-llm`, `settings-routing-python`, `settings-palette-{name}` (one per palette swatch, where `{name}` is the palette identifier).
- AC2.3: TopBar has testids: `topbar-sidebar-toggle`, `topbar-panel-plan`, `topbar-panel-editor`, `topbar-panel-flow`, `topbar-panel-monitor`, `topbar-panel-settings`, `topbar-chat-toggle`, `topbar-theme-toggle`.
- AC2.4: Running `npx tsc --noEmit` in `studio/` passes with no new errors after all additions.
- AC2.5: The Studio application renders identically in dev mode before and after the additions — `data-testid` attributes are inert and add no logic.
- AC2.6: No existing class names, inline styles, or event handlers are removed or modified; only `data-testid` props are added.

### Edge cases

- Palette swatches: if palette name contains spaces, replace with hyphens for the testid variant.
- If a component is conditionally rendered (e.g., project card only when projects exist), the testid must still be present on the element whenever it is in the DOM.

---

## S3 — Pathly POMs

**As** Yafit,
**I want** Page Object Model classes for HomeScreen, Settings, and TopBar that inherit `SharedBasePage`,
**So that** glue actions and workflows can call stable, named methods instead of raw locators.

**Delivered by:** Conversation 3

### Acceptance criteria

- AC3.1: `poms/pathly/pages/home_screen_page.py` defines `HomeScreenPage(BasePage)` with locators bound to all AC2.1 testids and methods: `open_project(name: str)`, `click_new_project()`, `get_project_names() -> list[str]`.
- AC3.2: `poms/pathly/pages/settings_page.py` defines `SettingsPage(BasePage)` with locators bound to all AC2.2 testids and methods: `set_routing_engine(engine: str)`, `set_fsm_command(cmd: str)`, `save_settings()`.
- AC3.3: `poms/pathly/pages/top_bar_page.py` defines `TopBarPage(BasePage)` with locators bound to all AC2.3 testids and methods: `navigate_to_panel(panel: str)`, `toggle_chat()`, `toggle_theme()`.
- AC3.4: All three classes override the `url` property; the property returns the CDP target URL string (not an HTTP address). The `open()` method is a no-op with a docstring noting that navigation in Electron is handled by the CDP launcher, not URL loading.
- AC3.5: `poms/pathly/__init__.py` exists and exports all three page classes.
- AC3.6: All locator definitions use `data-testid` selectors exclusively (e.g., `page.locator('[data-testid="homescreen-new-project-btn"]')`).
- AC3.7: `HomeScreenPage.open_project(name)` raises `ValueError` if no project card with that name is found in the DOM.

### Edge cases

- `get_project_names()` must return an empty list (not raise) when HomeScreen shows no projects.
- `set_routing_engine(engine)` must raise `ValueError` if `engine` is not one of `["llm", "python"]`.

---

## S4 — Pathly glue actions + site register

**As** Yafit,
**I want** Stepper glue action modules for Pathly Studio and a `register.py` that auto-wires them into the engine,
**So that** workflow JSON files can call Pathly-specific actions by name without any manual wiring.

**Delivered by:** Conversation 4

### Acceptance criteria

- AC4.1: `stepper/sites/pathly/pages/home_screen_action.py` defines `PathlyHomeScreen` with actions: `pathly_open_project`, `pathly_new_project`, `pathly_assert_projects`. Each action is registered with the Stepper action registry.
- AC4.2: `stepper/sites/pathly/pages/settings_action.py` defines `PathlySettings` with actions: `pathly_set_routing`, `pathly_save_settings`. Each action is registered.
- AC4.3: `stepper/sites/pathly/pages/top_bar_action.py` defines `PathlyTopBar` with actions: `pathly_navigate_panel`, `pathly_toggle_chat`. Each action is registered.
- AC4.4: `stepper/sites/pathly/register.py` exports a `register(registry, screenshots_dir=None)` function that registers all three modules — matching the pattern of `sites/openlibrary/register.py` and `sites/saucedemo/register.py`.
- AC4.5: `stepper/sites/pathly/__init__.py` exists.
- AC4.6: `stepper/bootstrap/infra.py` `register_all_sites()` auto-discovers `stepper/sites/pathly/register.py` via the existing glob pattern with no manual addition required.
- AC4.7: A unit test imports `PathlyHomeScreen`, calls `pathly_open_project` with a mock page, and asserts the correct POM method is invoked.

### Edge cases

- `pathly_assert_projects` receives `extra.expected_names` as a list; it must fail the step (not silently pass) if any expected name is absent from the DOM.
- `pathly_navigate_panel` must validate that `extra.panel` is one of `["plan", "editor", "flow", "monitor", "settings"]` before clicking, and fail the step with a clear message if not.

---

## S5 — Smoke workflow end-to-end

**As** Yafit,
**I want** a runnable smoke workflow JSON that drives Pathly Studio from HomeScreen through all main panels,
**So that** I have a single repeatable command to verify the UI is not broken before committing.

**Delivered by:** Conversation 5

### Acceptance criteria

- AC5.1: `stepper/sites/pathly/workflows/pathly_smoke.json` is valid workflow JSON (schema: `{name, description, variables, steps}`).
- AC5.2: The smoke workflow steps in order: wait for HomeScreen to be ready → open a named project (using `{{project_name}}` variable) → navigate to each of plan, editor, flow, monitor panels via TopBar → assert each panel rendered → exit cleanly.
- AC5.3: Running the smoke workflow against a live `npm run dev` session (Electron with `--remote-debugging-port=9222`) completes in under 60 seconds.
- AC5.4: `stepper/sites/pathly/workflows/pathly_settings.json` is valid workflow JSON that: navigates to settings → reads the current routing engine value → does NOT mutate the developer's settings (read-only assertions only).
- AC5.5: The smoke workflow exits with code 0 on success and non-zero on any step failure.
- AC5.6: Re-running the smoke workflow a second time without restarting Electron produces the same pass/fail result (idempotent).

### Edge cases

- If `{{project_name}}` does not match any project in HomeScreen, the workflow must fail at the `pathly_open_project` step with a clear message, not at a later step.
- If Electron is not running when the workflow starts, the CDP launcher error (from S1) surfaces immediately before any steps execute.

---

## S6 — Extension guide for future contributors

**As** a future Pathly maintainer,
**I want** concise documentation in the README covering how to add a new testid, POM method, and glue action for a Studio panel,
**So that** extending the harness takes under 15 minutes for a contributor who has not worked in this codebase before.

**Delivered by:** Conversation 5

### Acceptance criteria

- AC6.1: The stepper framework README (or a `stepper/sites/pathly/README.md`) contains a numbered walkthrough: (1) add `data-testid` in Studio, (2) add locator + method to the relevant POM, (3) add glue action, (4) use in a workflow JSON.
- AC6.2: Each step in the walkthrough includes a concrete before/after code snippet.
- AC6.3: The guide states the CDP launcher requirement (Electron must be running with `--remote-debugging-port=9222`) and the PowerShell command to start it.
- AC6.4: The guide documents the `data-testid` naming convention: `{component}-{element}-{variant}` all lowercase kebab.
