# Implementation Plan — stepper-pathly-ui

## Dependency chain

```
Conv 1 (CDP launcher)
  └─ Conv 3 (POMs) depends on Conv 1 + Conv 2
       └─ Conv 4 (glue + register) depends on Conv 3
            └─ Conv 5 (workflows + smoke) depends on Conv 4

Conv 2 (data-testids) — parallel with Conv 1, must finish before Conv 3
```

---

## Conversation 1 — Electron CDP launcher

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories fulfilled:** S1
**Blocks:** Conv 3, 4, 5

### Rationale

The Stepper framework currently has no path to connect to an Electron renderer. All existing browser launching goes through `pw.chromium.launch()` in `infra.py`. Without a CDP connector, no Pathly-specific Stepper work can be tested end-to-end.

### Files to create

| File | Purpose |
|---|---|
| `stepper/engine/browser/electron_launcher.py` | Async `launch_electron_cdp(port: int, timeout_ms: int) -> BrowserContext` |
| `stepper/sites/pathly/electron_config.py` | Constants: `DEFAULT_CDP_PORT = 9222`, `STARTUP_TIMEOUT_MS = 30000` |
| `tests/unit/test_electron_launcher.py` | Unit test with mocked CDP endpoint |

### Files to modify

| File | Change |
|---|---|
| `stepper/bootstrap/infra.py` | `launch_browser()` gains `browser_type: str = "chromium"` and `cdp_port: int = None` params; new branch calls `launch_electron_cdp` when `browser_type == "electron"` |
| `stepper/main.py` | CLI: add `--browser` (choices: chromium, electron) and `--cdp-port` args |
| `stepper/engine/runner/api.py` | `StepperSession.__init__` gains `electron_cdp_port: int = None`; passes it through to session context factory |

### Detailed tasks

1. Create `stepper/engine/browser/` directory if it does not exist. Add `__init__.py`.
2. Implement `launch_electron_cdp(port, timeout_ms)`:
   - Calls `async_playwright().start()` then `playwright.chromium.connect_over_cdp(f"http://localhost:{port}")`.
   - Wraps the call in a retry loop with 500ms sleep intervals up to `timeout_ms`.
   - On timeout: raises `ElectronLaunchError` with message: `"Could not connect to Electron on CDP port {port}. Is Electron running with --remote-debugging-port={port}?"`.
   - On success: returns `browser.contexts[0]`.
3. Create `electron_config.py` with `DEFAULT_CDP_PORT`, `STARTUP_TIMEOUT_MS`, and a `PATHLY_ELECTRON_EXECUTABLE` placeholder string.
4. Modify `infra.py` `launch_browser()` signature and add the electron branch.
5. Modify `main.py` CLI args.
6. Modify `StepperSession` to pass `electron_cdp_port` through.
7. Write unit test: mock `playwright.chromium.connect_over_cdp`; assert returned object is `browser.contexts[0]`; assert `ElectronLaunchError` raised when mock raises `ConnectionRefusedError`.

### Acceptance criteria (verified before Conv 2 begins)

- AC1.1 through AC1.6 from USER_STORIES.md all pass.
- `python -m pytest tests/unit/test_electron_launcher.py -q` exits 0.
- `python stepper/main.py --help` shows `--browser` and `--cdp-port` options.

---

## Conversation 2 — data-testid attributes in Studio

**Repo:** `C:\Users\Yafit\pathly-adapters\studio\`
**Stories fulfilled:** S2
**Blocks:** Conv 3

### Rationale

Zero `data-testid` attributes currently exist in the renderer. This conversation establishes the naming convention and seeds the initial set on the three MVP screens. It can run in parallel with Conv 1.

### Files to modify

| File | Elements to instrument |
|---|---|
| `studio/src/renderer/src/components/HomeScreen.tsx` | Tab buttons, new project button, project cards, open buttons, view toggles |
| `studio/src/renderer/src/components/Settings/index.tsx` | Save button, FSM command input, routing radio cards, palette swatches |
| `studio/src/renderer/src/components/topbar/index.tsx` | Sidebar toggle, panel nav buttons (plan/editor/flow/monitor/settings), chat toggle, theme toggle |

### Detailed tasks

1. Open each file. Identify the interactive elements matching the testid list in AC2.1–AC2.3.
2. Add `data-testid="..."` props. Do not change any other prop, class name, style, or handler.
3. For palette swatches where the name comes from a variable, derive the testid dynamically: `` data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} ``.
4. For `homescreen-project-card` and `homescreen-open-btn`, these appear inside a `.map()` — apply testid to the element in the map callback; no index suffix needed (Playwright can filter by visible text or nth).
5. Run `npx tsc --noEmit` from `studio/` and fix any type errors (there should be none — `data-testid` is a valid HTML attribute).
6. Visually confirm in `npm run dev` that nothing regressed.

### Acceptance criteria (verified before Conv 3 begins)

- AC2.1 through AC2.6 from USER_STORIES.md all pass.
- `npx tsc --noEmit` exits 0 in `studio/`.
- All 17 testids listed across HomeScreen, Settings, TopBar are findable via browser DevTools `document.querySelectorAll('[data-testid]')`.

---

## Conversation 3 — Pathly POMs

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories fulfilled:** S3
**Depends on:** Conv 1 (for BasePage import path patterns) + Conv 2 (testid names finalized)

### Rationale

POM classes are the stable abstraction layer between raw locators and the glue actions. They must mirror the `SharedBasePage` pattern used by openlibrary and saucedemo exactly, so future contributors can read any Pathly POM and recognize the pattern.

### Files to create

| File | Class |
|---|---|
| `poms/pathly/__init__.py` | Exports all three page classes |
| `poms/pathly/pages/__init__.py` | Empty or re-exports |
| `poms/pathly/pages/home_screen_page.py` | `HomeScreenPage(BasePage)` |
| `poms/pathly/pages/settings_page.py` | `SettingsPage(BasePage)` |
| `poms/pathly/pages/top_bar_page.py` | `TopBarPage(BasePage)` |

### Detailed tasks

1. Read `poms/shared/base_page.py` to confirm constructor signature and abstract interface before writing any subclass.
2. Read an existing POM (e.g., openlibrary or saucedemo) to confirm the override pattern for `url` and `open()`.
3. Implement `HomeScreenPage`:
   - `url` property returns `"electron://pathly-homescreen"` (a sentinel string; not a real URL — Electron navigation is by CDP, not URL loading).
   - `open()` is a no-op with docstring: `"Navigation handled by CDP launcher. This method is intentionally a no-op for Electron pages."`.
   - Locators defined as class-level `@property` methods using `[data-testid="..."]` selectors.
   - `open_project(name)`: finds all `homescreen-project-card` elements, matches by text content, clicks the sibling `homescreen-open-btn`. Raises `ValueError` if not found.
   - `click_new_project()`: clicks `homescreen-new-project-btn`.
   - `get_project_names()`: returns list of text contents of all `homescreen-project-card` elements; returns `[]` if none.
4. Implement `SettingsPage` analogously. `set_routing_engine(engine)` validates against `["llm", "python"]` before clicking. `set_fsm_command(cmd)` clears the input then fills. `save_settings()` clicks save and awaits network idle or a short sleep.
5. Implement `TopBarPage`. `navigate_to_panel(panel)` validates panel is one of `["plan", "editor", "flow", "monitor", "settings"]`. `toggle_chat()` and `toggle_theme()` are single-click methods.
6. Wire `poms/pathly/__init__.py` to export all three.

### Acceptance criteria (verified before Conv 4 begins)

- AC3.1 through AC3.7 from USER_STORIES.md all pass.
- `python -c "from poms.pathly import HomeScreenPage, SettingsPage, TopBarPage; print('ok')"` exits 0.
- All locators use `[data-testid="..."]` — grep confirms no `class=` or `id=` selectors in the three new POM files.

---

## Conversation 4 — Pathly glue actions + site register

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories fulfilled:** S4
**Depends on:** Conv 3

### Rationale

Glue action modules translate workflow JSON step `action` strings into POM method calls. The `register.py` hook makes Pathly auto-discoverable by `register_all_sites()` without touching `infra.py` beyond what Conv 1 already changed.

### Files to create

| File | Module / contents |
|---|---|
| `stepper/sites/pathly/__init__.py` | Empty |
| `stepper/sites/pathly/register.py` | `register(registry, screenshots_dir=None)` — calls each action module's `register` classmethod |
| `stepper/sites/pathly/pages/__init__.py` | Empty |
| `stepper/sites/pathly/pages/home_screen_action.py` | `PathlyHomeScreen` with 3 actions |
| `stepper/sites/pathly/pages/settings_action.py` | `PathlySettings` with 2 actions |
| `stepper/sites/pathly/pages/top_bar_action.py` | `PathlyTopBar` with 3 actions |
| `tests/unit/test_pathly_glue.py` | Unit test for `pathly_open_project` |

### Glue action signatures (each action receives `page, step, context`)

| Action name | Module | Calls POM method |
|---|---|---|
| `pathly_open_project` | HomeScreen | `HomeScreenPage.open_project(step.extra["project_name"])` |
| `pathly_new_project` | HomeScreen | `HomeScreenPage.click_new_project()` |
| `pathly_assert_projects` | HomeScreen | `HomeScreenPage.get_project_names()` + assert `step.extra["expected_names"]` subset |
| `pathly_set_routing` | Settings | `SettingsPage.set_routing_engine(step.extra["engine"])` |
| `pathly_save_settings` | Settings | `SettingsPage.save_settings()` |
| `pathly_navigate_panel` | TopBar | `TopBarPage.navigate_to_panel(step.extra["panel"])` |
| `pathly_toggle_chat` | TopBar | `TopBarPage.toggle_chat()` |

### Detailed tasks

1. Read one existing glue action module (e.g., openlibrary or saucedemo) to confirm the registration pattern (`@classmethod register(cls, registry)`).
2. Implement the three action modules following that pattern exactly.
3. Implement `stepper/sites/pathly/register.py`:
   ```python
   from stepper.sites.pathly.pages.home_screen_action import PathlyHomeScreen
   from stepper.sites.pathly.pages.settings_action import PathlySettings
   from stepper.sites.pathly.pages.top_bar_action import PathlyTopBar

   def register(registry, screenshots_dir=None):
       PathlyHomeScreen.register(registry)
       PathlySettings.register(registry)
       PathlyTopBar.register(registry)
   ```
4. Verify `register_all_sites()` in `infra.py` will discover `stepper/sites/pathly/register.py` via the glob — no code change needed if the glob is `sites/*/register.py`.
5. Write unit test: mock a `HomeScreenPage` instance; call `pathly_open_project` action with `extra={"project_name": "MyProject"}`; assert `open_project("MyProject")` was called on the mock.

### Acceptance criteria (verified before Conv 5 begins)

- AC4.1 through AC4.7 from USER_STORIES.md all pass.
- `python -c "from stepper.sites.pathly.register import register; print('ok')"` exits 0.
- `python -m pytest tests/unit/test_pathly_glue.py -q` exits 0.
- All 7 action names are present in the registry after `register_all_sites()` is called.

---

## Conversation 5 — Pathly workflows + smoke test

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories fulfilled:** S5, S6
**Depends on:** Conv 4

### Rationale

This conversation closes the loop: a human-runnable workflow JSON that proves the full stack works end-to-end, plus the extension guide so future contributors can grow the harness.

### Files to create

| File | Purpose |
|---|---|
| `stepper/sites/pathly/workflows/pathly_smoke.json` | Main smoke workflow |
| `stepper/sites/pathly/workflows/pathly_settings.json` | Settings read-only verification workflow |
| `stepper/sites/pathly/fixtures/` | Directory placeholder (empty `__init__.py`; fixture data in v2) |
| `stepper/sites/pathly/README.md` | Extension guide |

### Smoke workflow structure (`pathly_smoke.json`)

```json
{
  "name": "pathly-smoke",
  "description": "Launch Pathly Studio, open a project, navigate all main panels.",
  "variables": {
    "project_name": "my-test-project"
  },
  "steps": [
    { "action": "wait",            "description": "Wait for HomeScreen to be ready" },
    { "action": "pathly_open_project",  "description": "Open project {{project_name}}", "extra": { "project_name": "{{project_name}}" } },
    { "action": "pathly_navigate_panel", "description": "Navigate to plan panel",    "extra": { "panel": "plan" } },
    { "action": "screenshot",      "description": "Screenshot plan panel" },
    { "action": "pathly_navigate_panel", "description": "Navigate to editor panel",  "extra": { "panel": "editor" } },
    { "action": "screenshot",      "description": "Screenshot editor panel" },
    { "action": "pathly_navigate_panel", "description": "Navigate to flow panel",    "extra": { "panel": "flow" } },
    { "action": "screenshot",      "description": "Screenshot flow panel" },
    { "action": "pathly_navigate_panel", "description": "Navigate to monitor panel", "extra": { "panel": "monitor" } },
    { "action": "screenshot",      "description": "Screenshot monitor panel" }
  ]
}
```

### Settings workflow structure (`pathly_settings.json`)

```json
{
  "name": "pathly-settings-check",
  "description": "Navigate to Settings and assert current state without mutating config.",
  "variables": {},
  "steps": [
    { "action": "pathly_navigate_panel", "description": "Navigate to settings panel", "extra": { "panel": "settings" } },
    { "action": "screenshot",            "description": "Screenshot settings panel" }
  ]
}
```

### README contents (AC6 requirements)

The `stepper/sites/pathly/README.md` must cover:
1. Prerequisites: Electron running with `--remote-debugging-port=9222`. PowerShell command: `$env:ELECTRON_ENABLE_LOGGING=1; npm run dev -- --remote-debugging-port=9222` from `studio/`.
2. Running the smoke workflow: `python stepper/main.py --browser electron --cdp-port 9222 --workflow stepper/sites/pathly/workflows/pathly_smoke.json`.
3. Numbered walkthrough — adding one new element:
   - Step 1: Add `data-testid="myscreen-myelement"` to the React component in `pathly-adapters/studio/src/renderer/src/components/`.
   - Step 2: Add locator property and method to the relevant POM in `poms/pathly/pages/`.
   - Step 3: Add glue action to `stepper/sites/pathly/pages/<screen>_action.py` and register it in the action's `register()` classmethod.
   - Step 4: Add a step to the workflow JSON using the new action name.
4. `data-testid` naming convention: `{component}-{element}-{variant}` all lowercase kebab.
5. Note on settings safety: `pathly_settings.json` is read-only; do not add `pathly_save_settings` to automated workflows without a sandbox config dir.

### Detailed tasks

1. Write `pathly_smoke.json` following the exact schema from infra.py workflow loader.
2. Write `pathly_settings.json`.
3. Validate both files parse as valid JSON (`python -c "import json; json.load(open(...))"` exits 0).
4. Create `stepper/sites/pathly/fixtures/__init__.py`.
5. Write `stepper/sites/pathly/README.md` covering all AC6 items.
6. Manual smoke run: start Studio with `npm run dev` and `--remote-debugging-port=9222`; run smoke workflow; confirm exit code 0 and runtime under 60s.

### Acceptance criteria

- AC5.1 through AC5.6 and AC6.1 through AC6.4 from USER_STORIES.md all pass.
- Both workflow JSON files parse without error.
- Smoke workflow exit code is 0 on a live Studio session.
- Smoke run measured time is under 60 seconds.
- README contains all four numbered walkthrough steps and the PowerShell startup command.
