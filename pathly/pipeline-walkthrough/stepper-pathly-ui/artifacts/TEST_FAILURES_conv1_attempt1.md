# TEST_FAILURES — stepper-pathly-ui

Date: 2026-05-31
Tester: Claude Sonnet 4.6

---

## FAIL 1 — AC1.4: CLI --browser electron --cdp-port does not route to CDP launcher

**Criterion:** The CLI (`stepper/main.py`) accepts `--browser electron --cdp-port 9222` and routes to the CDP launcher.

**What failed:** The CLI arguments `--browser` and `--cdp-port` are parsed (lines 409–412 of `stepper/main.py`) but never passed to the `run()` function. The `run()` function always calls `launch_browser(_pw_instance, s.browser, headless, s.slow_mo)` using `s.browser` from the settings file, not from `args.browser`. The `run()` function signature (lines 100–113) has no `browser_type` or `cdp_port` parameters. The result is that `--browser electron` has no effect when invoked via `python stepper/main.py`.

**Expected:** `python stepper/main.py --browser electron --cdp-port 9222 --workflow ...` connects to Electron via CDP.

**Actually happened:** The run always uses `s.browser` (default `"chromium"`) from settings; the `--browser electron` flag is silently ignored.

**Files:**
- `C:\Users\Yafit\playwright-stepper-framework\stepper\main.py` lines 440–451 (run() call — browser/cdp_port not forwarded)
- `C:\Users\Yafit\playwright-stepper-framework\stepper\bootstrap\infra.py` lines 23–34 (launch_browser accepts browser_type and cdp_port but they are never supplied from CLI path)

**Note:** `StepperSession(electron_cdp_port=...)` in `api.py` DOES work correctly for the programmatic API (AC1.3 PASS). The CLI path is the gap.

---

## FAIL 2 — AC3.3: TopBarPage missing `sidebar-nav-monitor` locator

**Criterion:** `TopBarPage` locators bound to topbar testids plus sidebar nav testids `sidebar-nav-settings` and `sidebar-nav-monitor` from BottomNav.

**What failed:** `poms/pathly/pages/top_bar_page.py` defines `_sidebar_nav_settings` (line 46) but does NOT define a locator for `sidebar-nav-monitor`.

**Expected:** `_sidebar_nav_monitor` property returning `self._page.locator('[data-testid="sidebar-nav-monitor"]')`.

**Actually happened:** No `sidebar-nav-monitor` locator exists anywhere in `poms/pathly/` (confirmed by grep returning no matches).

**File:** `C:\Users\Yafit\playwright-stepper-framework\poms\pathly\pages\top_bar_page.py` (missing locator after line 46)

---

## FAIL 3 — AC5.4: pathly_settings.json does not read the current routing engine value

**Criterion:** `stepper/sites/pathly/workflows/pathly_settings.json` reads the current routing engine value and does NOT mutate the developer's settings.

**What failed:** The workflow contains only two steps — `pathly_navigate_panel` (navigate to settings) and `screenshot`. There is no step that reads or asserts the current routing engine value.

**Expected:** A step such as `assert_visible` or a custom assertion step targeting `settings-routing-llm` or `settings-routing-python` to confirm the current routing engine is readable.

**Actually happened:** The workflow only navigates to settings and takes a screenshot. The routing engine value is captured visually in the screenshot but is not read or asserted programmatically.

**File:** `C:\Users\Yafit\playwright-stepper-framework\stepper\sites\pathly\workflows\pathly_settings.json`

---

## Passing summary (for reference)

- AC1.1, AC1.2, AC1.3, AC1.5, AC1.6: PASS (unit tests pass; error message includes port 9222; StepperSession has electron_cdp_port; launcher is config-driven)
- AC2.1: PASS (all 8 HomeScreen testids present in Studio source; tabs are dynamically generated from `['projects', 'getting-started', 'settings']`)
- AC2.2: PASS (all 4 Settings testids present; palette testids dynamically generated with space-to-hyphen)
- AC2.3: PASS (all 5 TopBar testids present; sidebar-nav-settings and sidebar-nav-monitor in BottomNav.tsx)
- AC2.4: PASS (tsc --noEmit exits 0)
- AC3.1: PASS (HomeScreenPage has all required locators and methods including ValueError on missing project)
- AC3.2: PARTIAL — SettingsPage.set_routing_engine raises ValueError for invalid engines but accepts "python-fsm" in addition to ["llm", "python"]. AC3.2 specifies only `["llm", "python"]` as valid. This is a minor discrepancy — the implementation is more permissive than specified.
- AC3.3: FAIL (sidebar-nav-monitor locator missing — see FAIL 2 above)
- AC3.4: PASS (all three POMs override url property; open() is a no-op with docstring)
- AC3.5: PASS (poms/pathly/__init__.py exports all three page classes)
- AC3.6: PASS (all locators use data-testid selectors; no CSS/ID selectors found)
- AC3.7: PASS (open_project raises ValueError)
- AC4.1–AC4.5: PASS (all action files exist, all 7 actions registered, __init__.py exists)
- AC4.6: PASS (register_all_sites globs sites/*/register.py automatically)
- AC4.7: PASS (unit tests pass: test_open_project_calls_pom_method, test_assert_projects_fails_when_project_missing)
- AC5.1: PASS (pathly_smoke.json is valid JSON with name/description/variables/steps)
- AC5.2: PASS (smoke workflow steps: wait → open_project → navigate flow → screenshot → navigate monitor → screenshot → navigate settings → screenshot)
- AC5.3: SKIP (requires live Electron session)
- AC5.4: FAIL (settings.json does not programmatically read routing engine value — see FAIL 3)
- AC5.5: SKIP (requires live Electron session)
- AC5.6: SKIP (requires live Electron session)
- AC6.1: PASS (README.md at stepper/sites/pathly/README.md has 4-step walkthrough)
- AC6.2: PASS (4 code blocks with language tags; concrete code snippets for each step)
- AC6.3: PASS (CDP requirement stated; PowerShell startup command present with --remote-debugging-port=9222)
- AC6.4: PASS (naming convention documented: {component}-{element}-{variant} all lowercase kebab)
