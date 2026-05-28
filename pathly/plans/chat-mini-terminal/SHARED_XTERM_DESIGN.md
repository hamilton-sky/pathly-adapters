# ADR: Shared xterm instance per tabId (chat card ↔ full terminal)

Status: Implemented (2026-05-28)
Date: 2026-05-28
Feature: `chat-mini-terminal`
Scope: `studio/src/renderer/src/components/{ChatPanel,Terminal}/**`

## Refinement adopted during implementation: mutual exclusion

The "same-frame mount race" open question (§ Open questions #1 below) was
resolved by adopting a **mutual-exclusion rule** instead of a priority rule:

- **`fullShowingThisTab` = `open && (activeTabIdLeft === tabId || activeTabIdRight === tabId)`**
- When `fullShowingThisTab` is true → card cannot be in peek state. The
  card auto-collapses to banner. Min/Max button is hidden.
- When `fullShowingThisTab` is false → card respects the user's local
  `userViewState` (banner or peek). If peek, card hosts the xterm.

This kills the race because the question "who hosts the xterm?" has a single
source of truth: *is the full panel currently displaying this tab?* If yes →
full. If no → card (when user wants peek).

No same-frame coordination needed. Transitions are deterministic:
- Card peek → user clicks expand → openTab(tabId) → fullShowingThisTab flips
  to true → card detaches; full attaches.
- Full open → user closes panel (or switches tab) → fullShowingThisTab flips
  to false → full detaches; card re-attaches if user's viewState is peek.

The non-host card UX is now even simpler than the original §5 proposal: just
the banner preview row with the last line of `previewLines`. The "static
preview from scrollback" idea (rendering ~12 lines into a `<pre>`) was
dropped — the banner is enough, since the full panel has the live xterm
right there and there's no value showing a frozen mirror beside it.

## Implementation notes

- New module: `studio/src/renderer/src/components/Terminal/xtermRegistry.ts`
  — exports `getOrCreate`, `attachTo`, `detachFrom`, `dispose`, `getHost`,
  `fit`, `focus`, `write`, `getSelection`.
- `Terminal/index.tsx` — `tabInstancesRef` removed; `handleCloseTab` and
  `handlePopout` call `xtermRegistry.dispose`; `onExit` calls
  `xtermRegistry.write`. The "refit all on panel change" effect was
  removed — each `TerminalTabView` owns its own ResizeObserver, gated on
  `isHost`.
- `TerminalTabView.tsx` — `isHost = active && open`. Effects attach when
  hosting, detach otherwise. Right-click paste and drag-drop are bound only
  while hosting (full panel only).
- `MiniTerminalCard.tsx` — subscribes to `open`, `activeTabIdLeft`,
  `activeTabIdRight`. Derives `cardHosts = userViewState === 'peek' && !fullShowingThisTab`.
  Removed the scrollback-replay effect: the xterm's internal buffer persists
  across DOM moves, so no replay needed.
- `types.ts` — `TabInstance` interface removed (no callers).
- `PopoutTerminal.tsx` — unchanged. It runs in a separate renderer process
  (popout BrowserWindow), so its xterm instance is fully isolated.

The clipboard key handler (`attachCustomKeyEventHandler`) was moved into
`getOrCreate` so it's bound exactly once per xterm instance. Open question
#3 below (does it replace or stack?) becomes moot — we only ever call it
once per instance regardless.

---

## Original ADR — preserved below as the as-designed record



---

## Context

A PTY has exactly one `cols × rows` at any moment (`node-pty.IPty.resize(cols, rows)` —
see `studio/src/main/ipc/terminal.ts:115-120`). Today we mount **two independent
xterm instances against the same `tabId`**:

```
                       ┌───────────────────────────────┐
                       │     node-pty (single PTY)     │
                       │     cols × rows = ONE value   │
                       └───────────────────────────────┘
                                    ▲
        ┌───────────────────────────┴───────────────────────────┐
        │                                                       │
  ┌──────────────────┐                              ┌──────────────────┐
  │ MiniTerminalCard │  ResizeObserver → fit()      │ TerminalTabView  │
  │ (xterm A, 12px)  │  → resize(tabId, cA, rA) ◄──►│ (xterm B, 14px)  │
  │ chat panel       │  → resize(tabId, cB, rB)     │ full panel       │
  └──────────────────┘                              └──────────────────┘
        scrollback replay                              ipc onData → write
        store-driven                                   listener-driven
```

Both views call `fitAddon.fit()` then `window.pathly.terminal.resize(tabId, cols, rows)`
(`MiniTerminalCard.tsx:108-119`, `TerminalTabView.tsx:80-89` and `:94-105`). Whichever
fires last clobbers the PTY size for the other. The user-visible cycle:

1. Card opens at ~88 cols. PTY = 88×8. Card renders correctly.
2. Full terminal opens at ~200 cols. PTY = 200×24. **Card now reads ANSI sized for
   200 cols into its 88-col grid** — visual corruption.
3. Chat panel resize triggers card `fit()`. PTY = 88×8. Card looks right again,
   **full terminal renders 88×8 into a 200×24 grid** — full now broken.

This is fundamental, not a race. **Two xterm instances cannot share one PTY without
one of them silently lying about its dimensions.** No locking, debouncing, or
last-writer-wins scheme fixes it — the loser of any given resize is structurally
mis-sized until the next user action.

Additional cost of the dual-instance approach:
- 2× xterm WebGL/canvas memory per tab.
- Two `onData` listener paths into the renderer for the same channel (chat path
  via `appendScrollback`, full path via direct `xterm.write`) — `ChatPanel/index.tsx:228`
  and `TerminalTabView.tsx:112`. They stay in sync only because Electron's
  `ipcRenderer.on` delivers to every listener.
- Mini card replays full scrollback on every mount (`MiniTerminalCard.tsx:101-106`) —
  noticeable jank on long-running tabs.

The constraint forces a single xterm instance per `tabId`, re-parented between hosts.

---

## Decision

**One `XTerm` per `tabId`, owned by a module-level singleton. The DOM element is
moved between hosts via `appendChild`. Only the active host runs the ResizeObserver
and calls PTY resize.**

```
              ┌─────────────────────────────────────────┐
              │   xtermRegistry (module singleton)      │
              │   Map<tabId, XtermRecord>               │
              │                                         │
              │   { xterm, fitAddon, currentHost,       │
              │     ptyDisposer, dataDisposer }         │
              └─────────────────────────────────────────┘
                              ▲    ▲
                  host='card' │    │ host='full'
                              │    │
                  ┌───────────┴────┴──────────────┐
                  │                               │
            ┌───────────────┐             ┌─────────────────┐
            │ MiniTerminal  │             │ TerminalTabView │
            │ Card          │             │                 │
            │               │             │                 │
            │ active host?  │             │ active host?    │
            │  ├─ yes: own  │             │  ├─ yes: own    │
            │  │  RO + fit  │             │  │  RO + fit    │
            │  └─ no: show  │             │  └─ no: empty   │
            │     static    │             │     placeholder │
            │     preview   │             │                 │
            └───────────────┘             └─────────────────┘
```

### 1. Instance location — module-level `xtermRegistry`

Promote the existing `tabInstancesRef` (currently a `useRef` inside
`Terminal/index.tsx:24`) to a true module-level singleton in a new file:

```
studio/src/renderer/src/components/Terminal/xtermRegistry.ts
```

```ts
// shape — illustrative only
interface XtermRecord {
  xterm: XTerm
  fitAddon: FitAddon
  currentHost: 'card' | 'full' | 'popout' | null  // who owns the DOM right now
  hostEl: HTMLDivElement | null                    // the DOM container it's parented under
  dataDisposer: IDisposable | null                 // xterm.onData → IPC write
  ptyUnsubscribe: (() => void) | null              // window.pathly.terminal.onData → xterm.write
  writtenScrollbackLen: number                     // for the static-preview path only
}

const records = new Map<string, XtermRecord>()

export function getOrCreate(tabId: string, opts: {...}): XtermRecord
export function attachTo(tabId: string, host: HostId, el: HTMLDivElement): void
export function detachFrom(tabId: string, host: HostId): void
export function dispose(tabId: string): void
```

**Why module-level, not Zustand:**
- xterm holds DOM/canvas + buffer state — not serializable, never belongs in store.
- React state would trigger re-renders on every host swap and lose the instance
  reference across `useRef` resets in StrictMode double-mounts.
- The existing `Terminal/index.tsx:24` already proves the pattern works; we're
  just hoisting it one scope up so `MiniTerminalCard` can reach it.

**Survives unmount because:** the `Map` lives in the module, not in any component.
`MiniTerminalCard` unmounting only calls `detachFrom('card')` (clears `dataDisposer`
if it owned it, removes the DOM node from the card container). The xterm itself
stays in the registry until either (a) the full panel attaches it next, or (b)
the tab is explicitly closed via `Terminal/index.tsx:95-101` (which still calls
`xterm.dispose()` + `terminal.kill`).

### 2. Host ownership — field on the registry record

`record.currentHost: 'card' | 'full' | 'popout' | null`.

Rejected alternatives:
- **Zustand field** — would cause every component subscribed to terminal state to
  re-render whenever a card opens/closes. The DOM move is already O(1); no React
  needs to know about it.
- **Inferred from DOM (`xterm.element.parentElement`)** — works but is fragile.
  Detection during the half-mounted state of a swap is racy.

The record field is the source of truth. Components consult
`xtermRegistry.getHost(tabId) === 'card'` to decide whether to render their xterm
container or a placeholder. Reads are synchronous; writes happen only at attach/detach.

### 3. DOM move mechanics

**Confirmed safe in this codebase already.** `TerminalTabView.tsx:72-78`:

```ts
if (containerRef.current && instance.container !== containerRef.current) {
  if (instance.xterm.element) {
    containerRef.current.appendChild(instance.xterm.element)
  } else {
    instance.xterm.open(containerRef.current)
  }
  instance.container = containerRef.current
}
```

This is the same pattern we extend. `xterm.element` is a stable DOM node;
`appendChild` on a new parent removes it from the old parent in the same tick.

**Exact attach sequence:**
```
attachTo(tabId, host, newEl):
  rec = records.get(tabId)
  if !rec.xterm.element:
     rec.xterm.open(newEl)                  // first-time open
  else:
     newEl.appendChild(rec.xterm.element)    // move
  rec.hostEl = newEl
  rec.currentHost = host
  requestAnimationFrame(() =>
     setTimeout(() => {
       rec.fitAddon.fit()
       cols = max(host === 'card' ? 40 : 1, rec.xterm.cols)
       if cols !== rec.xterm.cols: rec.xterm.resize(cols, rec.xterm.rows)
       void window.pathly.terminal.resize(tabId, cols, rec.xterm.rows)
       rec.xterm.focus()
     }, 0))
```

**Gotchas confirmed:**
- **Focus** — `appendChild` blurs the moved element. Re-focus inside the
  rAF+setTimeout(0) above, after the new container has been laid out.
- **Scroll position** — xterm preserves its internal buffer across reparenting;
  no `xterm.refresh()` needed. Verified: the existing reparent path in
  `TerminalTabView` does not call `refresh()` and works.
- **ResizeObserver** — observers attach to a DOM node. When we move the xterm
  element, the *container* node stays the same per host; only the observer
  the host owns gets disconnected on detach. See §4.
- **WebGL/canvas renderer** — xterm uses Canvas2D by default in this app (no
  WebGL addon loaded). Canvas elements survive reparenting; verified by the
  existing pattern.
- **`xterm.element` after `open()`** — populated on first `open()`. The fallback
  `xterm.open(newEl)` branch handles the first-mount case where no element
  exists yet.
- **Custom key handlers, event listeners** — `attachCustomKeyEventHandler` in
  `TerminalTabView.tsx:135-170` is attached per-mount and replaced on each
  mount. Move this attachment to the registry's `getOrCreate` so it survives
  host swaps. The container-level `mousedown`/`contextmenu`/drag listeners
  (`:209-220`) must be re-bound to the new container on every `attachTo`.

### 4. Resize ownership

```
Only the host that currently owns the xterm runs a ResizeObserver and calls
fitAddon.fit() + window.pathly.terminal.resize().
```

| Host           | Owns ResizeObserver? | Calls PTY resize? | At attach moment        |
|----------------|----------------------|-------------------|--------------------------|
| `card`         | yes, on card container | yes              | fit + resize in rAF+0ms |
| `full`         | yes, on full container | yes              | fit + resize in rAF+0ms |
| non-host       | no                   | no                | n/a                      |

Implementation rule: **the ResizeObserver lives inside the host component, not
in the registry record.** When the host mounts or becomes active, it creates
the observer and observes its container. When it unmounts or hands off ownership,
it disconnects.

At the moment of move:
- Old host calls `detachFrom(tabId, oldHost)`. Its ResizeObserver is already
  disconnected by its `useEffect` cleanup.
- New host calls `attachTo(tabId, newHost, newEl)`. After move completes, the
  new host runs its own initial `fit()` + PTY resize (the rAF+setTimeout step
  in §3).

Non-host card panel resizes happen all the time (chat panel drag handle
`useChatResize`). These must **not** trigger any fit when the card is not the
host. The host check is what enforces this — the card's RO callback gates on
`xtermRegistry.getHost(tabId) === 'card'` and no-ops otherwise. (Cheaper than
tearing the RO down and back up across host swaps.)

### 5. Non-hosting view's display

**When the card is not the host: render a static text preview from
`scrollbackByTabId`.**

The card already has the data (`MiniTerminalCard.tsx:74`):
```ts
const scrollback = useTerminalStore((s) => s.scrollbackByTabId[tabId] ?? [])
```

When not hosting, render the last N lines (peeled through the existing
`stripAnsi` in `ChatPanel/index.tsx:28-42`) into a plain `<pre>` inside the
132 px peek area. No xterm, no cursor, no input. Banner state behaves as today.

UX rationale:
- The peek area exists to confirm "something is happening" without stealing
  the full terminal's interactive surface.
- A static preview is honest about the state: the live cursor lives in the
  full panel. Re-mounting an xterm in the card just to look at it would
  re-trigger the very dual-instance bug we're fixing.
- `viewState: 'banner' | 'peek'` stays unchanged; only the contents of the
  peek-state div change based on host check.

When user clicks "open full terminal" from the card → registry detaches from
card, attaches to full. The card flips its render to static preview mode.
When user closes the full terminal → registry detaches from full; if the card
is still mounted, registry attaches back to card. Card flips back to live xterm.

### 6. Edge cases

**a) Card open → click "open full"**
- Card: `detachFrom('card')`; sets `currentHost = null` then `attachTo('full', el)`.
- Card auto-collapses banner → no, leave `viewState` alone. The user explicitly
  chose to move; the banner peek is now a static preview, which is the right
  visual cue. Auto-collapsing would be a surprise.
- Full panel opens via existing `openTab(tabId)` + `pathly:focus-terminal-tab`
  event (`ChatPanel/index.tsx:571-574`).

**b) Full open with active xterm → new chat message spawns mini card for same kind**
- The kind already has a `tabId`; `launchMiniTerminal` returns early
  (`ChatPanel/index.tsx:530-534`). No new instance created.
- Card mounts in static-preview mode because `xtermRegistry.getHost(tabId) === 'full'`.
- The card shows live data from `scrollbackByTabId` (already populated by the
  chat panel's `appendScrollback` subscription at `ChatPanel/index.tsx:228-229`).

**c) Popout window for same tabId**
- `terminal:popout` (`main/ipc/terminal.ts:133-179`) transfers ownership to the
  new BrowserWindow and re-loads the renderer with `?terminal=<tabId>`.
- The popout renderer is a **different `webContents`**, so its registry singleton
  is a different `Map`. From the original window's perspective, the xterm
  instance stays in its registry but is no longer reachable by PTY data —
  `ptyOwners` now points at the popup.
- Treatment: when the original window detects `terminal:exit` or sees its
  `terminal:data:<tabId>` channel go silent, the host (card or full) should
  call `xtermRegistry.dispose(tabId)`. The existing `handlePopout` in
  `Terminal/index.tsx:103-112` already disposes the xterm and removes the tab —
  extend that to also call `xtermRegistry.dispose`.
- The popout's renderer is a fresh registry; it creates its own instance via
  the same `getOrCreate` flow, hosting in a popout-mode UI. No third host
  inside the main window.

**d) User closes full terminal panel**
- Two sub-cases:
  - Tab closed via X (`Terminal/index.tsx:95-101`): PTY killed, registry
    disposed, card has no `tabId` anymore — `renderTerminalCard` returns null.
  - Full panel collapsed but tab still alive (`toggle()`): currently the
    panel just hides via CSS `display: none`. The registry record stays
    intact, the full host's `TerminalTabView` is still mounted (just hidden).
    Card sees `currentHost === 'full'` and stays in static preview.
- **Refinement**: when the full panel collapses and there is a mini card
  mounted for the same tabId, we should hand off back to the card. Two
  options:
  - **(i)** Full's `TerminalTabView` unmounts when panel closed → emits
    detach, card's mount-effect re-attaches. Requires full panel to actually
    unmount the `<TerminalTabView>` children when `open=false`, which is
    not currently the case (`Terminal/index.tsx:170` hides via `display: none`
    instead of conditional render).
  - **(ii)** Listen to `useTerminalStore.open` in the card; when it flips
    from `true → false`, request attach. Cleaner — no change to full
    panel's render strategy.

  Recommend (ii): subscribe to `open` in the card; on `open=false` and
  `currentHost === 'full'`, request `attachTo('card', cardEl)`. This keeps
  the full panel's "tabs survive while panel is hidden" behaviour intact.

**e) User closes mini card (X button) while full is open**
- Current X handler only sets `hiddenMiniCards` (`ChatPanel/index.tsx:575`).
  No dispose, no detach. **Keep this behaviour.** Hidden card just means
  React-unmounting the `<MiniTerminalCard>`. Registry is untouched. xterm
  stays parented in the full panel.
- If `currentHost === 'card'` at the moment of X (i.e., user closed card while
  full is *not* open), the card unmounts → its `useEffect` cleanup runs
  `detachFrom('card')`. The xterm element is now orphaned in the registry
  with `hostEl = null` and `currentHost = null`. PTY keeps running; data
  keeps appending to `scrollbackByTabId`. Reopening the card or opening the
  full panel re-attaches. **This is the same orphaned-instance state we
  already create when the panel closes; nothing new.**

**f) Multiple kinds (claude + codex + shell)**
- Each kind has its own `tabId`; registry is keyed by `tabId`. No interaction
  between kinds. Three separate xterm instances exist; each may be hosted
  in card *or* full independently.

**g) First-time open**
- `launchMiniTerminal` (`ChatPanel/index.tsx:528-542`) calls `addTabSilent` +
  `terminal.spawn`. Card mounts.
- Card's mount effect calls `xtermRegistry.getOrCreate(tabId, ...)`. No record
  exists → registry creates `XTerm + FitAddon`, returns record.
- Card calls `attachTo('card', containerEl)`. Registry runs `xterm.open(el)`
  because `xterm.element` is null. PTY IPC listener wired (`pathly.terminal.onData`)
  in registry, not in card.
- User clicks "open full" → `attachTo('full', fullEl)`. Same path, except now
  `xterm.element` is populated, so the branch is `appendChild`. **One code
  path, two branches**, exactly as the existing `TerminalTabView.tsx:73-77`
  already does.

### 7. Migration path

Self-contained. No feature flag needed — this fixes a visible bug; we want it
on by default. Sequence:

**Step A — extract registry.** New file
`studio/src/renderer/src/components/Terminal/xtermRegistry.ts`. Move the body
of `tabInstancesRef`-using code from `Terminal/index.tsx` and `TerminalTabView.tsx`
into module-scope functions: `getOrCreate`, `attachTo`, `detachFrom`, `dispose`.
At this step, behaviour is unchanged — both views still use the same registry,
but only the full panel knows about it.

**Step B — point card and full at the registry.** Replace
`MiniTerminalCard.tsx:81-143` (the entire `useEffect` that creates its own
`new XTerm()`) with `attachTo('card', containerRef.current)`. Replace the
identical pattern in `TerminalTabView.tsx:54-91` with `attachTo('full', containerRef.current)`.
Both views now operate on the same instance — **this alone fixes the data
race because there's no second xterm to write into**. Resize race still
exists (both still call `fit`).

**Step C — gate resize on `currentHost`.** Move ResizeObservers from inside
each view's effect to be host-gated. Card's RO callback checks
`getHost(tabId) === 'card'` before fitting. Same for full. The DOM move
itself emits the host swap.

**Step D — switch non-host card display to static preview.** When
`getHost(tabId) !== 'card'`, render a `<pre>` with the last N lines from
`scrollbackByTabId[tabId]` instead of the xterm container. Card stays mounted
to receive future host attachments; only the inner contents differ.

**Step E (optional cleanup).** Remove the chat panel's bespoke
`appendScrollback`-via-card-replay logic in `MiniTerminalCard.tsx:101-156`.
Once the registry owns the PTY listener, the card no longer needs to replay
scrollback into xterm — it either *is* the host (xterm has the buffer) or
*is not* the host (renders from store). `scrollbackByTabId` is kept solely
to drive the static preview.

**Single PR feasibility.** Steps A–D are tightly coupled (Step B alone leaves
the resize race; Step C alone is meaningless without B). Ship as one commit,
behind no flag. Step E can be a follow-up commit.

### 8. What stays the same

- **`terminalStore.scrollbackByTabId`** — still source of truth for the
  static preview. Still appended to in `ChatPanel/index.tsx:228-229` via
  the existing IPC subscription.
- **PTY IPC contract** (`spawn`/`write`/`resize`/`onData`/`onExit`/`popout`/`kill`)
  in `main/preload/index.ts:48-70` and `main/ipc/terminal.ts:57-180` —
  zero changes.
- **`ptyOwners` ownership check** in main — unchanged. Single-renderer
  ownership remains a security boundary.
- **`addTabSilent`** in `terminalStore.ts:109-116` — unchanged. Still how
  the chat panel registers tabs without stealing focus.
- **Full panel UX** (`Terminal/index.tsx`) — panel toggle, split, tabs,
  popout, keyboard shortcut all unchanged. Only the inner per-tab view
  swaps its instance source.
- **Custom key handlers** for copy/paste — moved to registry, semantically
  unchanged.

---

## Consequences

**Improves:**
- Fixes the dual-instance resize race fundamentally — there is only one
  `cols × rows` per `tabId`, set by exactly one component at a time.
- 1× xterm memory per tab instead of 2× (mini cards are no longer xterm
  instances; they're text previews when not hosting).
- No more "replay all scrollback into card xterm on every mount" jank
  (`MiniTerminalCard.tsx:101-105`) — card either *is* the live xterm or
  shows lines directly.
- Single PTY data listener path. Today both `ChatPanel/index.tsx:228` and
  `TerminalTabView.tsx:112` subscribe to `terminal:data:<tabId>`. After
  Step E, registry is the only xterm-writing subscriber; chat-panel
  subscription continues but only feeds `scrollbackByTabId`.
- Aligns with the existing `tabInstancesRef` pattern that already proved
  cross-mount persistence works.

**More complex:**
- Module-level singleton with explicit lifecycle. Easy to leak xterm
  instances if `dispose` is forgotten — needs careful audit of every
  `closeTab` path (currently `Terminal/index.tsx:95-101` and `:103-112`).
- DOM move sequence has timing sensitivities (rAF + setTimeout 0 + fit).
  Documented in §3, but breakable by future refactors that change the
  layout effect order.
- Host transitions need explicit hand-off events. Today both views can
  independently exist without talking; tomorrow they coordinate via the
  registry. Race scenarios when card and full mount in the same frame
  (e.g., on app start with a saved layout) need either deterministic
  priority ("full wins if both mount in same tick") or a clear "last
  caller wins" rule. Recommend: **last `attachTo` wins**, which matches
  intuition — whichever view rendered most recently is what the user is
  looking at.

**Perf:**
- DOM `appendChild` of an existing xterm element is O(1) plus one canvas
  paint after `fit()`. Imperceptible.
- Avoiding the double scrollback replay should remove a noticeable hitch
  on tabs with thousands of lines.
- ResizeObserver is per-host (1 per active view), not per-instance — no
  change in observer count.

---

## Alternatives considered

**(a) Two xterm instances + coordinated resize lock / last-writer-wins.**
Rejected. The PTY has one size; whichever instance "loses" is mis-sized
until the next user interaction. Locking only narrows the race window;
it does not eliminate the mis-sized state. Also doesn't address the 2×
memory or double-replay cost.

**(b) Virtual xterm running in a worker, both views render snapshots.**
Rejected. xterm.js is not worker-compatible (relies on DOM Canvas). Even
with a custom serializer, the active interactive view still needs a real
xterm with key/mouse handlers — back to square one. Excessive complexity
for a problem solved by `appendChild`.

**(c) Canvas/screenshot mirror of the primary xterm into the secondary.**
Rejected. Could work for the non-hosting view's preview, but is strictly
worse than rendering plain text from scrollback (more code, lossy on
non-monospace anti-aliasing across DPRs, no text selection). Plain `<pre>`
with `scrollbackByTabId` wins on simplicity.

**(d) Keep two instances, fork the IPC channel so each has its own PTY.**
Rejected. Would mean spawning two PTYs per tab (one Claude per chat, one
Claude per full). Defeats the whole point of the chat panel as a peek into
the same session. Also breaks the single-`ptyOwners` ownership model.

---

## Open questions

1. **Same-frame mount race.** If both the card and full panel mount in the
   same tick on app startup (e.g., persisted layout with full panel `open=true`
   and an active chat-spawned tab), which wins? Recommend declaring "last
   `attachTo` call wins, full panel runs its mount effect after card by
   convention because it's rendered later in the tree" — but this depends
   on React's child-mount ordering being stable. Verify with a test before
   relying on it; otherwise add an explicit priority rule.

2. **Static preview line count.** Card peek area is 132 px. With 12 px font
   + 1.2 line-height, that's ~9 lines visible. Recommend rendering the last
   ~12 lines (a touch over) and letting CSS clip overflow, so the latest
   line is always pinned to the bottom and partial scroll-up is visible.
   Confirm with the planner that this UX is acceptable vs. e.g. only
   showing the last 8.

3. **Custom key handler registration.** `attachCustomKeyEventHandler` in
   `TerminalTabView.tsx:135-170` is called inside a per-mount `useEffect`.
   xterm.js docs are not explicit about whether calling
   `attachCustomKeyEventHandler` a second time *replaces* the previous one
   or stacks. If it stacks, moving it into `getOrCreate` (called once per
   instance) is mandatory, not just an optimisation. **Worth verifying in
   the xterm.js source before implementing Step A.**

4. **Issue I spotted while reading:** `MiniTerminalCard.tsx:118` calls
   `window.pathly.terminal.resize(tabId, cols, rows)` from the chat-panel
   webContents. `terminal.ts:115-116` gates resize on
   `ptyOwners.get(tabId) === event.sender.id`. The chat panel and full
   panel are the *same* webContents (same main window), so this works
   today. **But the popout flow** (`terminal.ts:133-179`) *transfers*
   ownership to the popup window. After popout, a mini card still mounted
   in the main window will silently fail every resize call (return early
   at `:116`) and never write to the PTY. With the shared-instance
   refactor, this is benign because the popout window now owns the
   instance entirely — but worth a regression test: after popout, the
   main window's card must dispose its registry record cleanly.

5. **Should `scrollbackByTabId` stop being chunk-based (`string[]`) and
   become a single rolling string?** Today `appendScrollback` slices to
   the last 400 chunks (`terminalStore.ts:121-127`). With chunks of
   varying size, "last 400 chunks" is unpredictable line-count. For the
   static preview's "last 12 lines" requirement, a line-based store
   would be cleaner. Out of scope for this ADR, but worth flagging.
