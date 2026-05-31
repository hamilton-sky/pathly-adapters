# Architecture Proposal — stepper-pathly-ui

---

## 1. Repo map

### playwright-stepper-framework

```
stepper/
  engine/
    browser/
      __init__.py
      electron_launcher.py        ← new: async CDP connector, no Pathly imports
    runner/
      api.py                      ← modified: StepperSession gains electron_cdp_port param
  bootstrap/
    infra.py                      ← modified: launch_browser() gains browser_type + cdp_port
  main.py                         ← modified: --browser and --cdp-port CLI args
  sites/
    pathly/
      __init__.py                 ← new
      electron_config.py          ← new: constants only (port, timeout, executable path)
      register.py                 ← new: auto-discovery entry point
      pages/
        __init__.py               ← new
        home_screen_action.py     ← new: PathlyHomeScreen glue class
        settings_action.py        ← new: PathlySettings glue class
        top_bar_action.py         ← new: PathlyTopBar glue class
      workflows/
        pathly_smoke.json         ← new
        pathly_settings.json      ← new
      fixtures/
        __init__.py               ← new (placeholder)
      README.md                   ← new

poms/
  pathly/
    __init__.py                   ← new: exports all three page classes
    pages/
      __init__.py                 ← new
      home_screen_page.py         ← new: HomeScreenPage(BasePage)
      settings_page.py            ← new: SettingsPage(BasePage)
      top_bar_page.py             ← new: TopBarPage(BasePage)

tests/
  unit/
    test_electron_launcher.py     ← new
    test_pathly_glue.py           ← new
```

### pathly-adapters

```
studio/
  src/renderer/src/components/
    HomeScreen.tsx                ← modified: data-testid attrs added
    Settings/index.tsx            ← modified: data-testid attrs added
    topbar/index.tsx              ← modified: data-testid attrs added
```

No new files are created in pathly-adapters. All test infrastructure lives in
playwright-stepper-framework. The only changes in pathly-adapters are the
`data-testid` attribute additions — one prop per element, nothing else.

---

## 2. Layer diagram

```
Electron process  (npm run dev -- --remote-debugging-port=9222)
  │
  │  CDP wire protocol (HTTP + WebSocket on port 9222)
  ▼
electron_launcher.py  →  playwright.chromium.connect_over_cdp("http://localhost:9222")
  │                       returns BrowserContext (browser.contexts[0])
  ▼
StepperSession  (stepper/engine/runner/api.py)
  │  holds: page, context, registry, screenshots_dir
  ▼
GlueAction  (e.g. home_screen_action.PathlyHomeScreen.pathly_open_project)
  │  receives: page, step, context
  │  instantiates POM, delegates to POM method
  ▼
POM  (e.g. poms/pathly/pages/home_screen_page.HomeScreenPage)
  │  holds: Playwright page reference
  │  defines: locators via [data-testid="..."] selectors
  ▼
Playwright locator API  →  page.locator('[data-testid="homescreen-open-btn"]')
  │
  │  Playwright sends CDP commands to renderer
  ▼
DOM element with  data-testid="homescreen-open-btn"
  (rendered by React in the Electron renderer process)
```

Data flows top-down only. The workflow JSON drives `StepperSession`, which
routes to a glue action, which calls a POM, which issues a locator query, which
reaches the DOM via CDP.

---

## 3. Dependency direction

```
workflow JSON
  → StepperSession  (engine layer)
    → GlueAction    (sites/pathly/pages/*_action.py)
      → POM         (poms/pathly/pages/*.py)
        → BasePage  (poms/shared/base_page.py)
          → Playwright page object

electron_launcher.py
  ← StepperSession  (StepperSession calls the launcher; launcher knows nothing of sessions)
  ← infra.py        (launch_browser() calls launcher when browser_type == "electron")
  ← electron_config.py  (launcher imports constants from here; not the reverse)

register.py
  ← infra.py register_all_sites()  (auto-discovered by glob; register.py never imports infra)
```

Hard rules that must not be violated:

- POM files (`poms/pathly/`) do NOT import anything from `stepper/sites/pathly/`.
- Glue files (`stepper/sites/pathly/pages/`) do NOT import workflow JSON or
  `infra.py`. They import only their corresponding POM class.
- `electron_launcher.py` does NOT import `electron_config.py` at the top level
  — constants are passed in as arguments so the launcher remains generic.
  Callers (`infra.py`) read `electron_config.py` and pass the values through.
- `register.py` does NOT import `infra.py`. It only imports the three action
  classes and calls their `register` classmethods.

---

## 4. Key design decisions

### 4.1 Why CDP over Python Playwright's native Electron API

Python Playwright has no native Electron launch API. The JavaScript Playwright
library ships `electron.launch()`, but this API was never ported to the Python
bindings (as of Playwright Python 1.x). The CDP path —
`playwright.chromium.connect_over_cdp(endpoint)` — is the officially supported
cross-language alternative: Electron exposes a Chrome DevTools Protocol endpoint
when launched with `--remote-debugging-port`, and Playwright can attach to any
CDP-compatible target regardless of whether it is a browser or an Electron
renderer. This approach also has the advantage of connecting to an already-running
Electron dev session, which matches the developer's normal workflow (Studio
started with `npm run dev`).

### 4.2 Why `electron_launcher.py` is generic (no Pathly imports)

`electron_launcher.py` accepts `port` and `timeout_ms` as arguments and knows
nothing about Pathly Studio. This means any future Electron app (a different
product, a test harness for another tool) can use the same launcher by passing
different constants. Pathly-specific knowledge — the default port, the
executable path, the startup timeout — lives exclusively in
`stepper/sites/pathly/electron_config.py`. The caller (`infra.py`) reads
`electron_config.py` and passes the values through. If a second Electron app is
wired in, only a new `*_config.py` is needed; `electron_launcher.py` is
unchanged (AC1.6).

### 4.3 Why `open()` is a no-op in Pathly POMs

In a standard web POM, `open()` calls `page.goto(self.url)` to load the page.
In Electron, navigation between screens is controlled by the application itself
(React state, IPC events, router). There is no URL to navigate to from outside
the process. The CDP connection lands on whatever screen is currently displayed.
Making `open()` a no-op with an explanatory docstring prevents accidental
`page.goto()` calls that would either fail silently or navigate away from the
current renderer state. The `url` property is still implemented (returning a
sentinel string) so the `BasePage` abstract interface is satisfied without
raising `NotImplementedError`.

### 4.4 Why Conv 1 and Conv 2 can run in parallel

Conv 1 touches only `playwright-stepper-framework`. Conv 2 touches only
`pathly-adapters/studio`. There are zero shared files between the two
conversations. The only coupling is a naming contract: Conv 3 (POMs) must use
the testid strings that Conv 2 finalizes. That contract is already settled in
USER_STORIES.md (AC2.1–AC2.3) and is available to Conv 3 as written
specification, not as a file dependency. Parallelizing Conv 1 and Conv 2
saves one full sequential build slot.

### 4.5 Why Conv 3 depends on Conv 2

The POM locator definitions reference `data-testid` attribute values by name
(e.g., `[data-testid="homescreen-open-btn"]`). These strings must match exactly
what is in the DOM. If Conv 2 has not yet been committed and the testids are
still under discussion or partially applied, Conv 3 would write locators that
target attributes that may not exist or may have different names. Conv 2 must
be merged — or at minimum its testid list must be finalized and verified with
`npx tsc --noEmit` — before Conv 3 begins writing locator strings.

---

## 5. Conversation dependency graph

```
Conv 1 (CDP launcher)  ──────────────────────────────┐
                                                      ▼
Conv 2 (data-testids)  ──────────────────────────► Conv 3 (POMs)
                                                      │
                                                      ▼
                                                  Conv 4 (glue + register)
                                                      │
                                                      ▼
                                                  Conv 5 (workflows + smoke)
```

Linear reading:

- Conv 1 and Conv 2 are independent and can run in parallel.
- Conv 3 requires both Conv 1 (BasePage import path patterns confirmed) and
  Conv 2 (testid strings finalized).
- Conv 4 requires Conv 3 (POM classes exist and are importable).
- Conv 5 requires Conv 4 (glue actions and register are wired).

No conversation can be reordered past these constraints without breaking an
import or a locator reference.
