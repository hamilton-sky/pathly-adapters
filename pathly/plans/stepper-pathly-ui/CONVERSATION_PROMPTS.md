# Conversation Prompts — stepper-pathly-ui

Each prompt is self-contained. The builder must read the referenced files before starting work.

---

## Conv 1 — Electron CDP launcher

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories:** S1
**Done criteria:** `python -m pytest tests/unit/test_electron_launcher.py -q` exits 0; `python stepper/main.py --help` shows `--browser` and `--cdp-port`.

---

Build the Electron CDP launcher for the Playwright Stepper framework.

Context files to read first:
- `stepper/bootstrap/infra.py` — read `launch_browser()` and `register_all_sites()` carefully.
- `stepper/engine/runner/api.py` — read `StepperSession.__init__` and `__aenter__`.
- `stepper/main.py` — read current CLI argument definitions.
- Any one existing site's module (e.g., `stepper/sites/saucedemo/` or `stepper/sites/openlibrary/`) — for structural reference only.

Work to do:

1. Create directory `stepper/engine/browser/` with `__init__.py`.

2. Create `stepper/engine/browser/electron_launcher.py`:
   - Define `ElectronLaunchError(Exception)`.
   - Implement `async def launch_electron_cdp(port: int, timeout_ms: int = 30000) -> BrowserContext`:
     - Calls `async_playwright().start()` then `playwright.chromium.connect_over_cdp(f"http://localhost:{port}")`.
     - Retries every 500ms up to `timeout_ms` total.
     - On timeout raises `ElectronLaunchError("Could not connect to Electron on CDP port {port}. Is Electron running with --remote-debugging-port={port}?")`.
     - On success returns `browser.contexts[0]`.

3. Create `stepper/sites/pathly/electron_config.py`:
   ```python
   DEFAULT_CDP_PORT: int = 9222
   STARTUP_TIMEOUT_MS: int = 30000
   PATHLY_ELECTRON_EXECUTABLE: str = ""  # Set to absolute path for packaged app; leave empty for npm run dev
   ```

4. Modify `stepper/bootstrap/infra.py` `launch_browser()`:
   - Add params `browser_type: str = "chromium"` and `cdp_port: int = None`.
   - When `browser_type == "electron"`: import and call `launch_electron_cdp(port=cdp_port or DEFAULT_CDP_PORT)`.
   - Existing chromium path unchanged.

5. Modify `stepper/main.py`:
   - Add `--browser` arg with `choices=["chromium", "electron"]`, default `"chromium"`.
   - Add `--cdp-port` arg, type int, default `9222`.
   - Pass both through to session/infra layer.

6. Modify `stepper/engine/runner/api.py` `StepperSession`:
   - Add `electron_cdp_port: int = None` to `__init__`.
   - Pass it to the context factory so `launch_browser` receives `browser_type="electron"` and `cdp_port=electron_cdp_port` when set.

7. Create `tests/unit/test_electron_launcher.py`:
   - Test 1: mock `playwright.chromium.connect_over_cdp` to return a mock browser with `contexts[0]` set; assert `launch_electron_cdp` returns that context.
   - Test 2: mock raises `ConnectionRefusedError`; assert `ElectronLaunchError` is raised after retries; assert error message contains the port number.

Constraints:
- Do not alter any existing test files.
- Do not modify the openlibrary or saucedemo site configs.
- The launcher core in `electron_launcher.py` must have no Pathly-specific imports — it is generic. Pathly constants live only in `electron_config.py`.

---

## Conv 2 — data-testid attributes in Studio

**Repo:** `C:\Users\Yafit\pathly-adapters\studio\`
**Stories:** S2
**Done criteria:** `npx tsc --noEmit` exits 0 in `studio/`; all 20 testids present in the renderer DOM.

---

Add `data-testid` attributes to three Studio renderer components. This establishes the test ID convention for the entire project.

Context files to read first:
- `studio/src/renderer/src/components/HomeScreen.tsx`
- `studio/src/renderer/src/components/Settings/index.tsx`
- `studio/src/renderer/src/components/topbar/index.tsx`
- `studio/CLAUDE.md` — read UI coding rules before editing any component

Naming convention: `{component}-{element}-{variant}` — all lowercase kebab.

Work to do:

**HomeScreen.tsx** — add these testids:
- Tab button "Projects": `data-testid="homescreen-tab-projects"`
- Tab button "Getting Started": `data-testid="homescreen-tab-getting-started"`
- Tab button "Settings": `data-testid="homescreen-tab-settings"`
- "New project" button: `data-testid="homescreen-new-project-btn"`
- Each project card container: `data-testid="homescreen-project-card"`
- Each "Open" button inside a card: `data-testid="homescreen-open-btn"`
- Grid view toggle button: `data-testid="homescreen-view-grid-btn"`
- List view toggle button: `data-testid="homescreen-view-list-btn"`

**Settings/index.tsx** — add these testids:
- Save button: `data-testid="settings-save-btn"`
- FSM server command input: `data-testid="settings-fsm-command-input"`
- Routing engine radio/card "LLM": `data-testid="settings-routing-llm"`
- Routing engine radio/card "Python": `data-testid="settings-routing-python"`
- Each palette swatch: `` data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} `` (derive `name` from whatever identifier the swatch already uses)

**topbar/index.tsx** — add these testids:
- Sidebar toggle button: `data-testid="topbar-sidebar-toggle"`
- Plan panel button: `data-testid="topbar-panel-plan"`
- Editor panel button: `data-testid="topbar-panel-editor"`
- Flow panel button: `data-testid="topbar-panel-flow"`
- Monitor panel button: `data-testid="topbar-panel-monitor"`
- Settings panel button: `data-testid="topbar-panel-settings"`
- Chat toggle button: `data-testid="topbar-chat-toggle"`
- Theme toggle button: `data-testid="topbar-theme-toggle"`

Constraints:
- Add only `data-testid` props. Do not modify any existing prop, class name, style, event handler, or logic.
- Do not add a `data-testid` index suffix to repeated elements (project cards, open buttons) — Playwright will filter by text or `nth()`.
- After all changes run `npx tsc --noEmit` from `studio/` and fix any errors before finishing.
- Do not commit. User will review before committing.

---

## Conv 3 — Pathly POMs

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories:** S3
**Done criteria:** `python -c "from poms.pathly import HomeScreenPage, SettingsPage, TopBarPage; print('ok')"` exits 0; grep of new POM files shows only `[data-testid=` selectors, no `class=` or `id=`.

---

Build the three Pathly Page Object Model classes following the existing `SharedBasePage` pattern.

Context files to read first:
- `poms/shared/base_page.py` — read constructor, abstract `url`, `open()`, `wait_for_ready()`, `_interact()`.
- Any one existing POM (e.g., from openlibrary or saucedemo) — read how it overrides `url` and `open()`.
- `C:\Users\Yafit\pathly-adapters\pathly\plans\stepper-pathly-ui\USER_STORIES.md` — read AC3.1–AC3.7 for all method signatures and behavior.

Work to do:

1. Create `poms/pathly/__init__.py`:
   ```python
   from poms.pathly.pages.home_screen_page import HomeScreenPage
   from poms.pathly.pages.settings_page import SettingsPage
   from poms.pathly.pages.top_bar_page import TopBarPage

   __all__ = ["HomeScreenPage", "SettingsPage", "TopBarPage"]
   ```

2. Create `poms/pathly/pages/__init__.py` (empty).

3. Create `poms/pathly/pages/home_screen_page.py` — `HomeScreenPage(BasePage)`:
   - `url` property: returns `"electron://pathly-homescreen"`.
   - `open()`: no-op. Docstring: "Navigation handled by CDP launcher. This method is intentionally a no-op for Electron pages."
   - Locator properties (using `self.page.locator('[data-testid="..."]')`):
     - `_tab_projects`, `_tab_getting_started`, `_tab_settings`
     - `_new_project_btn`
     - `_project_cards` (all matching `homescreen-project-card`)
     - `_open_btns` (all matching `homescreen-open-btn`)
     - `_view_grid_btn`, `_view_list_btn`
   - `open_project(name: str)`: iterate `_project_cards`, match by `.inner_text()`, click the sibling `_open_btns`. Raise `ValueError(f"Project '{name}' not found in HomeScreen")` if not found.
   - `click_new_project()`: clicks `_new_project_btn`.
   - `get_project_names() -> list[str]`: returns `[card.inner_text() for card in _project_cards.all()]`; returns `[]` if none.

4. Create `poms/pathly/pages/settings_page.py` — `SettingsPage(BasePage)`:
   - `url` property: returns `"electron://pathly-settings"`. `open()`: no-op with same docstring.
   - Locators: `_save_btn`, `_fsm_command_input`, `_routing_llm`, `_routing_python`.
   - `set_routing_engine(engine: str)`: validates `engine in ["llm", "python"]`; raises `ValueError` if not; clicks `_routing_llm` or `_routing_python`.
   - `set_fsm_command(cmd: str)`: clears `_fsm_command_input`, fills with `cmd`.
   - `save_settings()`: clicks `_save_btn`.

5. Create `poms/pathly/pages/top_bar_page.py` — `TopBarPage(BasePage)`:
   - `url` property: returns `"electron://pathly-topbar"`. `open()`: no-op with same docstring.
   - Locators: `_sidebar_toggle`, `_panel_btns` (dict or individual properties for each panel), `_chat_toggle`, `_theme_toggle`.
   - `navigate_to_panel(panel: str)`: validates panel is in `["plan", "editor", "flow", "monitor", "settings"]`; raises `ValueError` if not; clicks `self.page.locator(f'[data-testid="topbar-panel-{panel}"]')`.
   - `toggle_chat()`: clicks `_chat_toggle`.
   - `toggle_theme()`: clicks `_theme_toggle`.

Constraints:
- All locators use `[data-testid="..."]` exclusively.
- Do not import from `stepper/` layer — POMs must be independent of the glue layer.
- Do not create test files in this conversation; unit tests belong in Conv 4.

---

## Conv 4 — Pathly glue actions + site register

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories:** S4
**Done criteria:** `python -m pytest tests/unit/test_pathly_glue.py -q` exits 0; all 7 required action names present in registry after `register_all_sites()`. (pathly_assert_panel_visible is optional — register it if implemented)

---

Build the Pathly glue action modules and site registration so the Stepper engine discovers Pathly automatically.

Context files to read first:
- `stepper/bootstrap/infra.py` — read `register_all_sites()` to confirm the glob pattern.
- Any one existing glue action module from openlibrary or saucedemo — read the `@classmethod register(cls, registry)` pattern and how actions are structured.
- `poms/pathly/pages/home_screen_page.py`, `settings_page.py`, `top_bar_page.py` — for method names.
- `C:\Users\Yafit\pathly-adapters\pathly\plans\stepper-pathly-ui\USER_STORIES.md` — AC4.1–AC4.7 for action names and validation rules.

Work to do:

1. Create `stepper/sites/pathly/__init__.py` (empty).

2. Create `stepper/sites/pathly/pages/__init__.py` (empty).

3. Create `stepper/sites/pathly/pages/home_screen_action.py` — `PathlyHomeScreen`:
   - Action `pathly_open_project`: reads `step.extra["project_name"]`, calls `HomeScreenPage.open_project(name)`.
   - Action `pathly_new_project`: calls `HomeScreenPage.click_new_project()`.
   - Action `pathly_assert_projects`: reads `step.extra["expected_names"]` (list); calls `get_project_names()`; asserts every expected name is in the result; fails step with message listing missing names if any are absent.
   - `@classmethod register(cls, registry)`: registers all three action names.

4. Create `stepper/sites/pathly/pages/settings_action.py` — `PathlySettings`:
   - Action `pathly_set_routing`: reads `step.extra["engine"]`; calls `SettingsPage.set_routing_engine(engine)`.
   - Action `pathly_save_settings`: calls `SettingsPage.save_settings()`.
   - `@classmethod register(cls, registry)`: registers both.

5. Create `stepper/sites/pathly/pages/top_bar_action.py` — `PathlyTopBar`:
   - Action `pathly_navigate_panel`: reads `step.extra["panel"]`; calls `TopBarPage.navigate_to_panel(panel)` (validation done inside POM).
   - Action `pathly_toggle_chat`: calls `TopBarPage.toggle_chat()`.
   - Action `pathly_assert_panel_visible` (bonus, optional): reads `step.extra["panel"]`; asserts `[data-testid="topbar-panel-{panel}"]` is visible.
   - `@classmethod register(cls, registry)`: registers all registered actions.

6. Create `stepper/sites/pathly/register.py`:
   ```python
   from stepper.sites.pathly.pages.home_screen_action import PathlyHomeScreen
   from stepper.sites.pathly.pages.settings_action import PathlySettings
   from stepper.sites.pathly.pages.top_bar_action import PathlyTopBar

   def register(registry, screenshots_dir=None):
       PathlyHomeScreen.register(registry)
       PathlySettings.register(registry)
       PathlyTopBar.register(registry)
   ```

7. Create `tests/unit/test_pathly_glue.py`:
   - Test: create a mock `HomeScreenPage` instance; call `pathly_open_project` with `step.extra = {"project_name": "MyProject"}` and the mock page; assert `open_project("MyProject")` was called on the mock.
   - Test: call `pathly_assert_projects` with `expected_names = ["A", "B"]`; mock `get_project_names()` to return `["A"]`; assert the step fails with a message mentioning "B".

Constraints:
- Follow the existing glue module structure exactly — do not invent new patterns.
- Do not modify `infra.py` beyond what Conv 1 already changed.
- Do not touch the openlibrary or saucedemo modules.

---

## Conv 5 — Pathly workflows + smoke test

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`
**Stories:** S5, S6
**Done criteria:** Both workflow JSON files parse as valid JSON; README contains all four walkthrough steps and PowerShell startup command; smoke run exits 0 in under 60s against a live Studio session.

---

Write the Pathly smoke workflow, settings workflow, and extension guide README. Then run the smoke to verify end-to-end.

Context files to read first:
- `stepper/bootstrap/infra.py` — read the workflow JSON loader to confirm exact schema fields required.
- Any one existing workflow JSON from openlibrary or saucedemo — read its structure.
- `stepper/sites/pathly/register.py` — confirm all action names available.
- `C:\Users\Yafit\pathly-adapters\pathly\plans\stepper-pathly-ui\USER_STORIES.md` — AC5.1–AC5.6 and AC6.1–AC6.4.

Work to do:

1. Create `stepper/sites/pathly/workflows/` directory.

2. Create `stepper/sites/pathly/workflows/pathly_smoke.json`:
   ```json
   {
     "name": "pathly-smoke",
     "description": "Launch Pathly Studio, open a project, navigate all main panels.",
     "variables": {
       "project_name": "my-test-project"
     },
     "steps": [
       { "action": "wait", "description": "Wait for HomeScreen to be ready", "extra": { "timeout": 5000 } },
       { "action": "pathly_open_project", "description": "Open project {{project_name}}", "extra": { "project_name": "{{project_name}}" } },
       { "action": "pathly_navigate_panel", "description": "Navigate to plan panel",    "extra": { "panel": "plan" } },
       { "action": "screenshot",           "description": "Screenshot plan panel" },
       { "action": "pathly_navigate_panel", "description": "Navigate to editor panel",  "extra": { "panel": "editor" } },
       { "action": "screenshot",           "description": "Screenshot editor panel" },
       { "action": "pathly_navigate_panel", "description": "Navigate to flow panel",    "extra": { "panel": "flow" } },
       { "action": "screenshot",           "description": "Screenshot flow panel" },
       { "action": "pathly_navigate_panel", "description": "Navigate to monitor panel", "extra": { "panel": "monitor" } },
       { "action": "screenshot",           "description": "Screenshot monitor panel" }
     ]
   }
   ```
   Adjust field names to match the exact schema from the workflow loader you read.

3. Create `stepper/sites/pathly/workflows/pathly_settings.json`:
   ```json
   {
     "name": "pathly-settings-check",
     "description": "Navigate to Settings panel and screenshot current state. Read-only — does not mutate developer config.",
     "variables": {},
     "steps": [
       { "action": "pathly_navigate_panel", "description": "Navigate to settings panel", "extra": { "panel": "settings" } },
       { "action": "screenshot",            "description": "Screenshot settings panel" }
     ]
   }
   ```

4. Validate both JSON files: `python -c "import json; json.load(open('stepper/sites/pathly/workflows/pathly_smoke.json'))"` and same for settings. Fix any parse errors.

5. Create `stepper/sites/pathly/fixtures/__init__.py` (empty placeholder for v2 fixture data).

6. Create `stepper/sites/pathly/README.md` with these sections:

   **Prerequisites**
   - Python 3.x with Playwright installed.
   - Pathly Studio checked out at `C:\Users\Yafit\pathly-adapters\studio\`.
   - Start Studio with CDP enabled (PowerShell):
     ```powershell
     cd C:\Users\Yafit\pathly-adapters\studio
     $env:ELECTRON_ENABLE_LOGGING=1
     npm run dev -- --remote-debugging-port=9222
     ```
   - Wait for the HomeScreen to appear before running workflows.

   **Running the smoke workflow**
   ```powershell
   cd C:\Users\Yafit\playwright-stepper-framework
   python stepper/main.py --browser electron --cdp-port 9222 --workflow stepper/sites/pathly/workflows/pathly_smoke.json
   ```

   **Adding a new element to the harness (4 steps)**

   Step 1 — Add data-testid in Studio (in `pathly-adapters` repo):
   Open the relevant component in `studio/src/renderer/src/components/`. Add `data-testid="myscreen-myelement"` to the target JSX element. Run `npx tsc --noEmit` to confirm no errors.

   Step 2 — Add locator and method to the POM (in this repo):
   Open `poms/pathly/pages/<screen>_page.py`. Add a locator property:
   ```python
   @property
   def _my_element(self):
       return self.page.locator('[data-testid="myscreen-myelement"]')
   ```
   Add a method that uses it.

   Step 3 — Add a glue action (in this repo):
   Open `stepper/sites/pathly/pages/<screen>_action.py`. Add an action function and register it in the `register()` classmethod.

   Step 4 — Use in a workflow:
   Add a step to the relevant workflow JSON:
   ```json
   { "action": "my_new_action", "description": "Do the thing", "extra": { "param": "value" } }
   ```

   **data-testid naming convention**
   Format: `{component}-{element}-{variant}` — all lowercase kebab.
   Examples: `homescreen-tab-projects`, `topbar-panel-flow`, `settings-routing-llm`.

   **Settings safety note**
   `pathly_settings.json` is read-only. Do not add `pathly_save_settings` to automated workflows without first setting up a sandbox config directory. Writing to the developer's real Pathly config from a test is not supported in v1.

7. Manual smoke run: start Studio in another terminal with CDP enabled; run the smoke command; verify exit code 0 and elapsed time under 60s. Record result in a comment at the top of this conversation.

Constraints:
- Do not start Electron from within the Python workflow — assume it is already running.
- Do not modify the workflow loader or infra.py.
- If the smoke run fails, diagnose and fix before marking the conversation done.
- Do not commit. User reviews before committing.
