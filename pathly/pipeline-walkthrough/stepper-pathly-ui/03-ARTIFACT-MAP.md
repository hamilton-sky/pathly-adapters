# 03 — Artifact Map: stepper-pathly-ui

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| `IMPL_QUESTIONS_conv2_attempt1.md` | Builder (Conv 2) | Orchestrator / scope adjustment | Three topbar testids had no DOM buttons; resolved by adding sidebar BottomNav testids for settings/monitor and marking plan/editor out of scope |
| `REVIEW_FAILURES_conv5_attempt1.md` | Reviewer | Builder (fix conversation) | 9 violations: V1–V7 missing `type="button"` and inline styles across topbar/HomeScreen/IconButton; V8 POM validation mismatch (`"python-fsm"`); V9 StepperSession not calling `register_all_sites` |
| `TEST_FAILURES_conv1_attempt1.md` | Tester | Builder (fix conversation) | 3 failures: AC1.4 CLI `--browser electron` arg not forwarded to `run()`; AC3.3 `sidebar-nav-monitor` locator missing from TopBarPage; AC5.4 pathly_settings.json did not programmatically read routing engine value |

---

## Source files changed

Files changed across both repos for this feature (pathly-adapters/studio + playwright-stepper-framework).

### pathly-adapters (this repo — studio changes)

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/components/HomeScreen.tsx` | S2 | Added `data-testid` to tab buttons, new project button, project cards, open buttons, view toggles, done button, show-more button; added `type="button"` to all `<button>` elements |
| `studio/src/renderer/src/components/Settings/index.tsx` | S2 | Added `data-testid` to save button, FSM command input, routing radio cards, palette swatches |
| `studio/src/renderer/src/components/topbar/index.tsx` | S2 | Added `data-testid` to sidebar toggle, back button; added `type="button"` to back button |
| `studio/src/renderer/src/components/topbar/PanelNav.tsx` | S2 | Added `data-testid` to flow and monitor panel buttons; added `type="button"` to both |
| `studio/src/renderer/src/components/sidebar/shell/BottomNav.tsx` | S2 | Added `data-testid="sidebar-nav-settings"` and `data-testid="sidebar-nav-monitor"` |
| `studio/src/renderer/src/components/ui/IconButton.tsx` | S2 (review fix) | Added `type="button"` to the `<button>` element |

### playwright-stepper-framework (separate repo — all new files)

| File | Stories | What changed |
|---|---|---|
| `stepper/engine/browser/__init__.py` | S1 | New — package init |
| `stepper/engine/browser/electron_launcher.py` | S1 | New — `launch_electron_cdp()` with retry loop and `ElectronLaunchError` |
| `stepper/sites/pathly/electron_config.py` | S1 | New — `DEFAULT_CDP_PORT`, `STARTUP_TIMEOUT_MS`, `PATHLY_ELECTRON_EXECUTABLE` constants |
| `stepper/bootstrap/infra.py` | S1 | Modified — `launch_browser()` gains `browser_type` + `cdp_port` params; electron dispatch branch added |
| `stepper/main.py` | S1 | Modified — `--browser` and `--cdp-port` CLI args added; forwarding to `run()` fixed (after test failure) |
| `stepper/engine/runner/api.py` | S1, S4 | Modified — `StepperSession` gains `electron_cdp_port` param; `__aenter__` calls Pathly `register_all_sites` |
| `poms/pathly/__init__.py` | S3 | New — exports all three page classes |
| `poms/pathly/pages/__init__.py` | S3 | New — package init |
| `poms/pathly/pages/home_screen_page.py` | S3 | New — `HomeScreenPage(BasePage)` with all AC2.1 locators and methods |
| `poms/pathly/pages/settings_page.py` | S3 | New — `SettingsPage(BasePage)` with all AC2.2 locators and methods |
| `poms/pathly/pages/top_bar_page.py` | S3 | New — `TopBarPage(BasePage)` with all AC2.3 locators + `sidebar-nav-monitor` (added after test failure) |
| `stepper/sites/pathly/__init__.py` | S4 | New — package init |
| `stepper/sites/pathly/register.py` | S4 | New — `register(registry)` auto-discovery entry point |
| `stepper/sites/pathly/pages/__init__.py` | S4 | New — package init |
| `stepper/sites/pathly/pages/home_screen_action.py` | S4 | New — `PathlyHomeScreen` with 3 registered actions |
| `stepper/sites/pathly/pages/settings_action.py` | S4 | New — `PathlySettings` with 2 registered actions |
| `stepper/sites/pathly/pages/top_bar_action.py` | S4 | New — `PathlyTopBar` with 3 registered actions |
| `stepper/sites/pathly/workflows/pathly_smoke.json` | S5 | New — smoke workflow (wait → open project → navigate flow/monitor/settings → screenshots) |
| `stepper/sites/pathly/workflows/pathly_settings.json` | S5 | New — settings read-only verification workflow (fixed after test failure to assert routing engine) |
| `stepper/sites/pathly/fixtures/__init__.py` | S5 | New — placeholder |
| `stepper/sites/pathly/README.md` | S6 | New — 4-step extension guide with CDP launcher requirement and data-testid naming convention |
| `tests/unit/test_electron_launcher.py` | S1 | New — success path + timeout path with mocked CDP endpoint |
| `tests/unit/test_pathly_glue.py` | S4 | New — `pathly_open_project` and `pathly_assert_projects` unit tests |

---

## Artifact flow diagram

```
USER_STORIES.md          <-- what to build
       |
       v
IMPLEMENTATION_PLAN.md   <-- how to build it
       |
       v
CONVERSATION_PROMPTS.md  <-- exact builder prompts
       |
       v
PROGRESS.md              <-- which conversations done
       |
       v
RETRO.md                 <-- what we learned
       |
       v
lessons/LESSONS.md       <-- promoted patterns -> next planner
pipeline-walkthrough/stepper-pathly-ui/  <-- metrics record -> this folder
```
