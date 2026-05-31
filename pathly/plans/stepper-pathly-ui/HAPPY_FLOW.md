# Happy Flow — stepper-pathly-ui

This document walks through the ideal end-to-end path for the feature assuming
every command succeeds, every file is in the right place, and the Studio app is
running. No error cases are described here. For edge cases see USER_STORIES.md.

---

## Conversation 1 — Electron CDP launcher

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`

### What the developer runs

```powershell
# In playwright-stepper-framework/
python -m pytest tests/unit/test_electron_launcher.py -q
python stepper/main.py --help
```

### What happens step by step

1. The developer creates `stepper/engine/browser/__init__.py` and
   `stepper/engine/browser/electron_launcher.py`. The launcher defines
   `launch_electron_cdp(port, timeout_ms)` which calls
   `playwright.chromium.connect_over_cdp(f"http://localhost:{port}")` inside
   a retry loop, then returns `browser.contexts[0]`.

2. `stepper/sites/pathly/electron_config.py` is created with three constants:
   `DEFAULT_CDP_PORT = 9222`, `STARTUP_TIMEOUT_MS = 30000`, and
   `PATHLY_ELECTRON_EXECUTABLE` placeholder string. The launcher imports
   only the constants it needs — no Pathly business logic touches the launcher
   core.

3. `stepper/bootstrap/infra.py` `launch_browser()` gains `browser_type` and
   `cdp_port` parameters. When `browser_type == "electron"` it calls
   `launch_electron_cdp`; otherwise it follows the existing chromium path.

4. `stepper/main.py` grows `--browser` (choices: chromium, electron) and
   `--cdp-port` CLI args, wired through to `StepperSession`.

5. `StepperSession.__init__` gains `electron_cdp_port: int = None` and passes
   it to the session context factory.

6. The unit test mocks `playwright.chromium.connect_over_cdp`, asserts the
   returned object is `browser.contexts[0]`, and asserts `ElectronLaunchError`
   is raised when the mock raises `ConnectionRefusedError`.

### Success state

- `python -m pytest tests/unit/test_electron_launcher.py -q` prints `1 passed`
  and exits 0.
- `python stepper/main.py --help` shows `--browser` and `--cdp-port` in the
  options list.
- No existing tests regress.

---

## Conversation 2 — data-testid attributes in Studio

**Repo:** `C:\Users\Yafit\pathly-adapters\studio\`

This conversation runs in parallel with Conversation 1.

### What the developer runs

```powershell
# In pathly-adapters/studio/
npx tsc --noEmit
npm run dev
# Then in browser DevTools:
# document.querySelectorAll('[data-testid]').length
```

### What happens step by step

1. The developer opens `HomeScreen.tsx` and adds `data-testid` props to the
   eight elements listed in AC2.1: tab buttons, the new project button, project
   cards inside `.map()`, the Open button inside `.map()`, and the two view
   toggle buttons. No other props, class names, styles, or handlers are
   touched.

2. `Settings/index.tsx` receives four static testids (save button, FSM command
   input, two routing radio cards) and one dynamic testid per palette swatch:
   `` data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} ``.

3. `topbar/index.tsx` receives eight testids: sidebar toggle, five panel nav
   buttons, chat toggle, theme toggle.

4. `npx tsc --noEmit` runs and exits 0 — `data-testid` is a valid HTML
   attribute and introduces no type errors.

5. The developer opens `npm run dev` and visually confirms the Studio renders
   identically to before — the new attributes are inert.

### Success state

- `npx tsc --noEmit` exits 0 with no new errors.
- `document.querySelectorAll('[data-testid]')` in DevTools returns all 20
  elements (8 HomeScreen + 4 Settings + 8 TopBar, palette count varies).
- The Studio app is visually unchanged.

---

## Conversation 3 — Pathly POMs

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`

Depends on Conv 1 (for `BasePage` import paths) and Conv 2 (testid names
finalized).

### What the developer runs

```powershell
python -c "from poms.pathly import HomeScreenPage, SettingsPage, TopBarPage; print('ok')"
python -m pytest tests/ -q --co  # confirm no collection errors
grep -r "class=" poms/pathly/     # must return no output
```

### What happens step by step

1. The developer reads `poms/shared/base_page.py` to confirm the constructor
   signature and abstract method list, then reads an existing POM (e.g.,
   openlibrary) to confirm the `url` property and `open()` override pattern.

2. `poms/pathly/pages/home_screen_page.py` is created.
   - `url` returns `"electron://pathly-homescreen"` (sentinel string).
   - `open()` is a no-op with the standard docstring.
   - Locators are `@property` methods using `[data-testid="..."]` selectors.
   - `open_project(name)` finds all `homescreen-project-card` elements,
     matches by text, clicks the sibling `homescreen-open-btn`.
   - `click_new_project()` clicks `homescreen-new-project-btn`.
   - `get_project_names()` returns a list of text contents; returns `[]` if
     none are present.

3. `poms/pathly/pages/settings_page.py` is created analogously.
   - `set_routing_engine(engine)` validates against `["llm", "python"]` before
     clicking the matching radio card.
   - `set_fsm_command(cmd)` clears the input then fills it.
   - `save_settings()` clicks the save button.

4. `poms/pathly/pages/top_bar_page.py` is created.
   - `navigate_to_panel(panel)` validates the panel name is one of
     `["plan", "editor", "flow", "monitor", "settings"]` then clicks the
     matching topbar button.
   - `toggle_chat()` and `toggle_theme()` are single-click methods.

5. `poms/pathly/__init__.py` exports all three classes.

### Success state

- The import one-liner prints `ok` and exits 0.
- `grep -r "class=" poms/pathly/` returns no output — every locator uses
  `data-testid`.
- `python -m pytest tests/ -q --co` collects all existing tests without
  collection errors.

---

## Conversation 4 — Pathly glue actions + site register

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`

Depends on Conv 3.

### What the developer runs

```powershell
python -c "from stepper.sites.pathly.register import register; print('ok')"
python -m pytest tests/unit/test_pathly_glue.py -q
```

### What happens step by step

1. The developer reads an existing glue module (e.g., `saucedemo` or
   `openlibrary`) to confirm the `@classmethod register(cls, registry)`
   pattern.

2. Three action modules are created following that pattern exactly:
   - `home_screen_action.py` — `PathlyHomeScreen` with `pathly_open_project`,
     `pathly_new_project`, `pathly_assert_projects`.
   - `settings_action.py` — `PathlySettings` with `pathly_set_routing`,
     `pathly_save_settings`.
   - `top_bar_action.py` — `PathlyTopBar` with `pathly_navigate_panel`,
     `pathly_toggle_chat`.

3. `stepper/sites/pathly/register.py` is created. It imports the three classes
   and calls each `register()` classmethod in sequence.

4. The developer verifies that `register_all_sites()` in `infra.py` already
   globs `sites/*/register.py` — no code change is needed; the new file is
   auto-discovered.

5. `tests/unit/test_pathly_glue.py` is written: it mocks a `HomeScreenPage`
   instance, calls `pathly_open_project` with `extra={"project_name": "MyProject"}`,
   and asserts `open_project("MyProject")` was called on the mock.

### Success state

- The import one-liner prints `ok` and exits 0.
- `python -m pytest tests/unit/test_pathly_glue.py -q` prints `1 passed`.
- All 7 action names (`pathly_open_project`, `pathly_new_project`,
  `pathly_assert_projects`, `pathly_set_routing`, `pathly_save_settings`,
  `pathly_navigate_panel`, `pathly_toggle_chat`) appear in the registry after
  `register_all_sites()` is called.

---

## Conversation 5 — Pathly workflows + smoke test

**Repo:** `C:\Users\Yafit\playwright-stepper-framework\`

Depends on Conv 4.

### What the developer runs

```powershell
# Terminal 1 — start Studio with CDP port open
cd C:\Users\Yafit\pathly-adapters\studio
$env:ELECTRON_ENABLE_LOGGING=1
npm run dev -- --remote-debugging-port=9222

# Terminal 2 — run smoke workflow
cd C:\Users\Yafit\playwright-stepper-framework
python stepper/main.py --browser electron --cdp-port 9222 `
  --workflow stepper/sites/pathly/workflows/pathly_smoke.json

# Validate workflow JSON files parse
python -c "import json; json.load(open('stepper/sites/pathly/workflows/pathly_smoke.json'))"
python -c "import json; json.load(open('stepper/sites/pathly/workflows/pathly_settings.json'))"
```

### What happens step by step

1. `pathly_smoke.json` is written with `name`, `description`, `variables`
   (`project_name`), and a `steps` array: wait → open project →
   navigate to plan → screenshot → navigate to editor → screenshot →
   navigate to flow → screenshot → navigate to monitor → screenshot.

2. `pathly_settings.json` is written as a read-only two-step workflow:
   navigate to settings → screenshot. No mutation steps.

3. Both JSON files are validated with `json.load()` — both parse without error.

4. `stepper/sites/pathly/fixtures/__init__.py` is created as a directory
   placeholder for future fixture data.

5. `stepper/sites/pathly/README.md` is written covering: CDP prerequisite +
   PowerShell startup command, smoke run command, four-step numbered
   walkthrough for adding a new element, testid naming convention, and the
   read-only safety note for `pathly_settings.json`.

6. The developer starts Studio in Terminal 1. The Electron process opens
   `--remote-debugging-port=9222`. In Terminal 2 the smoke workflow launches,
   CDP connects immediately on the first retry, HomeScreen appears, the project
   is opened by name, all four panel navigation steps succeed with screenshots
   captured, the workflow exits with code 0. Total elapsed time is under
   60 seconds.

7. The developer runs the smoke workflow a second time without restarting
   Electron. The workflow passes again with the same result — idempotent.

### Success state

- Both workflow JSON files parse without error.
- Smoke workflow exits with code 0.
- Elapsed time is under 60 seconds.
- Running the smoke workflow a second time still exits 0.
- `stepper/sites/pathly/README.md` exists and contains all four walkthrough
  steps plus the PowerShell startup command.
