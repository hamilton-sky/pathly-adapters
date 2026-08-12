# Architecture Proposal — CLI Command Center (CliMonitorBar refinement)

> Role: architect · Stage: DESIGN · Feature: cli-command-center
> Scope: Studio (Electron/React renderer) · Layer: `studio/src/renderer/src/`
> Basis: `pathly/features/cli-command-center/DESIGN_REVIEW.md` + current source

---

## Preamble — the design review is partially stale

Before framing the architecture, one load-bearing fact: **most of the "purely
CSS" near-term steps in DESIGN_REVIEW.md are already in the current code.** The
review was written against an earlier `CliMonitorBar` (288px, "CLI Engines",
non-collapsible Code Intel). The code has since moved on. Builders who follow
the review literally will re-apply changes that already exist, or worse,
regress the encapsulation choice the code already made.

Verified against source on 2026-07-05:

| Review step | Prescription | Current source | Status |
|---|---|---|---|
| 1 | width 288 → 320 | `CliMonitorBar.module.css:6` = `320px` | **already done** |
| 1 | max-height 340 → 480 | `CliMonitorBar.module.css:106` = `480px` | **already done** |
| 2 | header "CLI Engines" → "Command Center" | `CliMonitorBar.tsx:113` = `Command Center` | **already done** |
| 4 | collapsible Code Intel | `CodeIntelControl.tsx:13` local `useState(false)` | **done, different design** |
| 5 | section reorder (Flow → CodeIntel → queue → active) | `CliMonitorBar.tsx:124-152` | **already matches** |
| 6 | `.rowPrimary` / `.rowSecondary` split | `CodeIntelControl` tsx+css | **already done** |
| 3 | add `.sectionLabelPrimary` / `.sectionLabelMeta` | absent from `CliMonitorBar.module.css` | **not done** |
| 7 | `.btn` 28→30 / 24→26 + `:disabled` rule | `FlowControlBar.module.css:20-21` = 28/24 | **not done** |
| 8 | `.flowSection` add `border-bottom` | `CliMonitorBar.module.css:16-18` padding only | **not done** |
| 9 | `.body` padding token | `CliMonitorBar.module.css:105` = `4px` | **not done** |

So the *real* remaining near-term surface is steps **3, 7, 8, 9** plus a
decision to **ratify or reverse** the collapse-state location the code already
chose (step 4). Everything else is a no-op confirm.

---

## Scope

### Files in scope — near-term

```
studio/src/renderer/src/components/
  CliMonitorBar/
    CliMonitorBar.module.css      steps 3, 8, 9   (CSS only)
    CliMonitorBar.tsx             step 3 wiring   (FLOW label class)
    CodeIntelControl.tsx          step 4 ratify   (no change recommended)
  HQ/FlowControlBar/
    FlowControlBar.module.css     step 7          (CSS only)
```

Note the path correction vs the task brief: `FlowControlBar` lives under
`components/HQ/FlowControlBar/`, and `CodeIntelControl` is a **flat pair inside
`CliMonitorBar/`** (`CodeIntelControl.tsx` + `.module.css`), not its own folder.
There is no `components/CodeIntelControl/` and no `components/FlowControlBar/`.

### Files touched — north-star (future, not this goal)

```
studio/src/renderer/src/
  store/uiStore.ts                     + one boolean flag (see naming caveat)
  components/CliCommandCenter/         NEW folder (modal + cards)
    CliCommandCenter.tsx
    CliCommandCenter.module.css
    FlowCard/{FlowCard.tsx,.module.css}
    EngineCard/{EngineCard.tsx,.module.css}
  components/CliMonitorBar/
    useSessionActions.ts               NEW hook (extract stop/open logic)
    CliMonitorBar.tsx                  consume useSessionActions; add expand icon
```

### Explicitly out of scope

- No FSM / HTTP / Python changes. This is a pure renderer concern.
- No `terminalStore` / `runnerStore` shape changes — both north-star cards read
  the existing shapes. Only `uiStore` gains one flag (north-star only).
- The existing full-board **`CommandCenter`** panel (`components/CommandCenter/`,
  `commandCenterStore`, `activePanel:'command-center'`) is **a different thing**
  from the north-star "CLI Command Center" modal. Do not conflate them (see
  Key Decision 4).

---

## Layer map (near-term, step-by-step)

Dependency legend: `→` means "imports / reads from".

```
CliMonitorBar.tsx
  → useCliMonitor (hook)         sessions/history/queue/pos/expand
  → useUiStore                   cliMonitorOpen, toggleCliMonitor
  → useTerminalStore (direct)    kill/updateStatus/close/open in SessionRow
  → FlowControlBar               (HQ) — flow lifecycle buttons
  → CodeIntelControl             self-contained collapsible block
  → SpawnQueuePanel              queue + caps
  → CliMonitorBar.module.css

FlowControlBar.tsx
  → useRunnerStore               status/topic/mode + setters
  → useUiStore                   lastUsedFlowPath (selected flow)
  → RunnerBtn / AbortConfirmStrip / ReroutePopover
  → FlowControlBar.module.css

CodeIntelControl.tsx
  → useCodeContextSettings       backend/reindex (Settings hook)
  → useAutoCommitSetting         (HQ/FlowControlBar hook)
  → local useState(open)         collapse state — LOCAL, not store
  → CodeIntelControl.module.css
```

Per step:

| Step | Layer | File | Cross-component dep? |
|---|---|---|---|
| **3a** — add `.sectionLabelPrimary` | CSS module | `CliMonitorBar.module.css` | none |
| **3b** — apply it to the FLOW label | TSX (1 className swap) | `CliMonitorBar.tsx:126` | none |
| **3c** — `.sectionLabelMeta` | CSS module | `CliMonitorBar.module.css` | **superseded** — see Decision 1; do NOT add, would duplicate `CodeIntelControl`'s own `.sectionToggle` |
| **7a** — `.btn` 28→30 / 24→26 | CSS module | `FlowControlBar.module.css:20-21` | none (RunnerBtn + mode toggle both read `.btn`) |
| **7b** — `.btn:disabled` rule | CSS module | `FlowControlBar.module.css` | none — `RunnerBtn` already sets native `disabled={!enabled}` (`RunnerBtn.tsx:37`), so the pseudo fires unconditionally |
| **8** — `.flowSection` border-bottom | CSS module | `CliMonitorBar.module.css:16` | **check redundancy** — `FlowControlBar` `.wrapper` already has `border-bottom` (`FlowControlBar.module.css:4`); adding a second one stacks two 1px lines |
| **9** — `.body` padding token | CSS module | `CliMonitorBar.module.css:105` | none |

Key observation: **every remaining near-term step is CSS-module-local except
step 3b, which is a single `className` swap.** Zero state changes, zero new
hooks, zero cross-store wiring. The layer graph above is unchanged by near-term
work — this is a styling pass, not an architecture change.

### Step 3b concrete wiring

`CliMonitorBar.tsx:126` currently:

```tsx
<div className={s.sectionLabel}>FLOW</div>
```

becomes:

```tsx
<div className={s.sectionLabelPrimary}>FLOW</div>
```

That is the only TSX edit in the near-term set. `ACTIVE` / `RECENT` keep
`.sectionLabel` (correct per review §4). `QUEUE` lives inside `SpawnQueuePanel`
and is untouched.

### Step 8 caveat (dependency-adjacent CSS risk)

`flowSection` wraps `FlowControlBar`, whose `.wrapper` already draws
`border-bottom: 1px solid var(--border)`. Adding `border-bottom` to
`.flowSection` too produces a doubled divider. **Recommendation:** apply the
`border-bottom` to `.flowSection` and *remove* it from `FlowControlBar`'s
`.wrapper`, OR (cleaner, lower blast radius) skip step 8 entirely since the
separator already exists. I recommend **skip step 8** — the visual goal (cap
the primary zone) is already met by the wrapper border. Builders should verify
in the running app before adding CSS that duplicates an existing line.

---

## North-star architecture

### Concept recap

Header "expand" icon (`Maximize2`) morphs the 320px floating panel into a
full-canvas modal listing every flow and every engine as cards. Escape /
outside-click / Cpu-button collapse back to the compact panel.

### Component tree

```
CliCommandCenter/                         (modal shell, z-index 950)
  CliCommandCenter.tsx
    ├─ reads useUiStore  → cliCommandCenterOpen (NEW flag) + setter
    ├─ reads useRunnerStore → status/stage (flow cards)
    ├─ reads useTerminalStore → tabs/history/spawnQueue (engine cards)
    ├─ reads useCliMonitor → sessions[] (elapsed + lastLines already derived)
    │
    ├─ FLOWS column
    │    └─ FlowCard/  (one per active flow session)
    │         └─ RunnerBtn        ← reused directly from HQ/FlowControlBar
    │
    └─ ENGINES column
         ├─ EngineCard/  (one per running + queued tab)
         │    └─ useSessionActions(tab)  ← NEW shared hook (stop/open)
         └─ SpawnQueuePanel  ← reused (limits block)
```

### State: what is new, what is reused

| Concern | Source | New? |
|---|---|---|
| flow status / stage | `useRunnerStore` | reused |
| engine tabs / history / queue | `useTerminalStore` | reused |
| derived elapsed + last output lines | `useCliMonitor` | reused |
| stop / open-terminal actions | `useSessionActions(tab)` | **new hook (extraction)** |
| modal open/close | `uiStore` | **one new boolean** |

**Exactly one new store field.** Everything else is derivable from existing
stores. This keeps the modal and the compact panel as two *views over one
state* — no risk of the two diverging, because there is no second copy of the
data.

### `useSessionActions` extraction

Today the stop/open logic is inlined inside `SessionRow` in
`CliMonitorBar.tsx:29-34`:

```tsx
const handleStop = () => {
  void window.pathly.terminal.kill(tab.id)
  useTerminalStore.getState().updateTabStatus(tab.id, 'done')
  useTerminalStore.getState().closeTab(tab.id)
}
const handleOpen = () => { useTerminalStore.getState().openTab(tab.id) }
```

Extract verbatim into `CliMonitorBar/useSessionActions.ts`:

```
useSessionActions(tab: TerminalTab) → { stop(): void, open(): void }
```

Then both `SessionRow` (compact) and `EngineCard` (modal) consume it. The
force-kill-before-onExit comment (the load-bearing reason `updateTabStatus`
precedes `closeTab`) must ride along into the hook — it documents a real PTY
lifecycle hazard, not a style choice. This extraction is safe to do **now**
as a pure refactor even before the modal exists; it reduces `CliMonitorBar.tsx`
(currently 156 lines, over the 150 guideline) toward compliance.

### Dependency direction of the new components

```
CliCommandCenter ─→ uiStore, runnerStore, terminalStore   (stores)
CliCommandCenter ─→ useCliMonitor, useSessionActions       (hooks)
FlowCard         ─→ RunnerBtn (HQ/FlowControlBar)          (leaf component)
EngineCard       ─→ useSessionActions                       (hook)
```

All arrows point **downward** (component → hook → store) and **sideways to
leaf components** (`RunnerBtn`). No hook imports a component; no store imports
a hook or component. This matches the renderer's implicit layer contract
(components → hooks/services → stores) — see Dependency audit below.

---

## Key decisions

### Decision 1 — Code-Intel collapse state: LOCAL (ratify current code)

The review (§4, build step 4) says: add `codeIntelOpen` to `useCliMonitor`,
render the CODE INTELLIGENCE label as a `<button className={sectionLabelMeta}>`
in `CliMonitorBar.tsx`, gate `<CodeIntelControl/>` on it.

The current code did the opposite and, I argue, **better**:
`CodeIntelControl.tsx:13` owns `const [open, setOpen] = useState(false)` and
renders its *own* `.sectionToggle` header + chevron internally.

**Recommendation: keep it local. Do not lift to `useCliMonitor`.**

Rationale:
- **Single responsibility.** The collapse is intrinsic to CodeIntelControl —
  no other component needs to read or set it. Lifting it to the shared monitor
  hook widens that hook's surface for zero benefit and couples `CliMonitorBar`
  to a child's internal disclosure state.
- **No cross-component consumer.** The CLAUDE.md hover/state rule ("never put
  ephemeral UI state in a shared location unless it must cross a component
  boundary") applies to disclosure state too. It does not cross a boundary.
- **The review's `sectionLabelMeta` class becomes dead.** Its entire job was to
  style a toggle that CodeIntelControl now styles itself via `.sectionToggle`.
  Adding `sectionLabelMeta` would be two classes for one control. **Drop
  step 3c.**

Trade-off accepted: the FLOW label (in `CliMonitorBar`) and the CODE
INTELLIGENCE label (in `CodeIntelControl`) are now styled by two different
class families in two files. That is acceptable — they live in different
components with different responsibilities. If visual drift becomes a problem,
promote the label typography to shared tokens, not to a shared class.

### Decision 2 — Transition animation approach (north-star)

Options for the compact↔modal morph:

```
A. CSS-only: two absolutely-positioned layers, opacity+scale transitions,
   toggled by a data-state attr driven by the uiStore flag.
B. JS-orchestrated (Framer-motion / manual RAF sequencing).
```

**Recommendation: A (CSS-only, `data-state` + `transition`).** The review's own
timings (panel out 80ms opacity+scale 0.98; modal in 120ms scale 1) are trivial
transitions. Electron/Chromium composites opacity+transform on the GPU, so this
stays off the main thread and needs no animation library. Drive it with the
existing token `--transition-fast` family plus one `--ease-out`. No new
dependency. This also matches the CLAUDE.md "no inline styles" rule — the only
per-element dynamic value would be a `data-state` attribute, not a `style` prop.

Avoid animating `width`/`height`/`left`/`top` (layout-triggering). Use
`transform: scale()` + `opacity` exclusively.

### Decision 3 — Component sharing strategy

`RunnerBtn` is imported directly by `FlowCard` (it is already a
props-driven leaf: `label/tooltip/enabled/onClick/children`). No wrapper, no
duplication. `EngineCard` shares the compact `SessionRow`'s behavior via
`useSessionActions`, not by importing `SessionRow` (their markup differs — a
card vs a row — but their *actions* are identical). This is the correct seam:
**share the behavior (hook), not the presentation (component).**

### Decision 4 — modal flag naming (avoid collision)

There is already a panel literally called **Command Center**
(`activePanel:'command-center'`, `components/CommandCenter/`,
`commandCenterStore`, `useCommandCenterStore`). The review names the new modal
"CLI Command Center" and proposes a `commandCenterOpen` flag in `uiStore`.

**Recommendation: name the new flag `cliCommandCenterOpen`** (not
`commandCenterOpen`) to avoid semantic collision with the existing full-board
CommandCenter. A grep for `commandCenter` already returns the board; a bare
`commandCenterOpen` would be actively misleading. This is cheap insurance —
name it distinctly from day one.

---

## Trade-offs and risks

### Near-term

- **CSS specificity — low risk.** All near-term changes are new class
  definitions or single-property edits inside CSS modules. CSS Modules scope
  class names per-file (hashed), so there is no global-cascade collision risk
  across `CliMonitorBar.module.css`, `FlowControlBar.module.css`, and
  `CodeIntelControl.module.css`. The only specificity concern is *within*
  `FlowControlBar.module.css`: `.btn:disabled` (step 7b) vs the existing
  `.btnDisabled` class (line 62) and `.btn:hover:not(:disabled)` (line 32).
  These compose cleanly — `:disabled` and `.btnDisabled` can coexist (RunnerBtn
  applies both), and `:hover:not(:disabled)` already guards hover. Verify the
  disabled Start button (idle→running edge) still dims correctly.
- **Doubled border (step 8)** — described above. Mitigation: skip step 8.
- **Touch-target bump (step 7a)** — 28→30 / 24→26 widens the flow row by
  ~2px × 8 buttons ≈ 16px + gaps. At 320px with `flex-wrap: wrap` the row may
  still wrap on the smallest window; the review claims the 320px width prevents
  wrap on the lifecycle group only. Acceptable — wrapping is graceful.
- **Stale-review risk (highest actual risk)** — a builder mechanically applying
  all 9 steps will regress Decision 1 (re-lifting state to the hook) and add
  dead CSS. Mitigation: this proposal is the build contract; the "already done"
  table above is the checklist.

### North-star

- **Modal lifecycle complexity.** Escape-key + outside-click + Cpu-button all
  collapse the modal — three dismiss paths converging on one `uiStore` setter.
  Risk: focus management and event-listener cleanup (keydown listener must be
  removed on unmount). Mitigation: single `useEffect` in `CliCommandCenter`
  owning the `keydown`/outside-click listeners, keyed on the open flag.
- **Animation perf on Electron — low if Decision 2 is followed.** Only if a
  builder animates layout props does this become a jank risk. Guardrail:
  transform+opacity only.
- **Two-view divergence — mitigated by design.** Because both views read the
  same stores (no copied state), they cannot show different truth. The only
  shared *logic* is `useSessionActions`, extracted once.
- **`CliMonitorBar.tsx` size.** Already 156 lines (>150 guideline). The
  `useSessionActions` extraction and eventually pulling `SessionRow`/`HistoryRow`
  into their own files should accompany north-star work to stay within the
  component-size rule.

---

## Dependency direction audit

The renderer's implicit layer contract (from `studio/CLAUDE.md` — components do
one job; state in Zustand stores; hooks own state+effects; no inline styles;
tokens from CSS):

```
components/  →  hooks/  →  services/  →  store/ (Zustand)
     │                                      ▲
     └──────────── read via selectors ──────┘
```

Confirmation for all changes in this proposal:

| Change | Imports introduced | Direction | Verdict |
|---|---|---|---|
| Near-term steps 3,7,8,9 | none (CSS + 1 className) | n/a | clean |
| `useSessionActions` (new hook) | `terminalStore`, `window.pathly.terminal` | hook → store/IPC | downward — OK |
| `CliCommandCenter` | uiStore, runnerStore, terminalStore, useCliMonitor, useSessionActions, RunnerBtn | component → hooks/stores/leaf | downward — OK |
| `FlowCard` | RunnerBtn (leaf) | component → leaf component | sideways — OK |
| `EngineCard` | useSessionActions | component → hook | downward — OK |
| `uiStore.cliCommandCenterOpen` | none | store leaf | OK |

**No upward imports.** No store imports a component or hook. No hook imports a
component. `RunnerBtn` is consumed as a leaf by both `FlowControlBar` and the
new `FlowCard` — that is horizontal reuse of a presentational leaf, not an
upward dependency. The near-term work introduces **no new import edges at all**.
The north-star work stays entirely inside the existing Electron/React renderer
layer and respects the component → hook → store direction.

---

## Build contract summary

**Do now (near-term):**
1. Step 3a+3b — add `.sectionLabelPrimary`, apply to FLOW label (`CliMonitorBar.tsx:126`).
2. Step 7 — `.btn` 28→30 / 24→26 + `.btn:disabled` rule (`FlowControlBar.module.css`).
3. Step 9 — `.body` padding → `var(--space-2) var(--space-1)` (`CliMonitorBar.module.css:105`).
4. **Skip** step 8 (doubled border) unless design confirms it wants the wrapper border moved.
5. **Skip** step 3c `.sectionLabelMeta` (superseded by `CodeIntelControl` `.sectionToggle`).
6. **Ratify** step 4 as-is (local collapse state) — no change.
7. Steps 1, 2, 5, 6 — already shipped; confirm only.

**Optional refactor (safe, unblocks north-star, improves size compliance):**
- Extract `useSessionActions(tab)` from `SessionRow`.

**Later (north-star, separate goal):**
- `CliCommandCenter/` + `FlowCard/` + `EngineCard/`, `uiStore.cliCommandCenterOpen`,
  header `Maximize2` expand icon, CSS-only transform+opacity morph.

No product input is blocked — all decisions above are resolvable from the
design review + source. No `HUMAN_QUESTIONS.md` written.
