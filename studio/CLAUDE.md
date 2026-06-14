# Studio — Frontend Layer

Electron + React + Vite desktop app. Visual flow builder and AI chat panel.

## Directory structure

```
studio/
  src/main/        Electron main process — IPC handlers, window management
  src/renderer/    React UI — components, stores (Zustand), styles
  tsconfig.web.json    renderer TypeScript config (used for type-checking)
  tsconfig.node.json   main-process TypeScript config
```

## Type-checking

Always run from the **repo root**, not from `studio/`:

```bash
# Renderer (React)
node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json

# Main process
node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json

# Renderer only (npm script — runs tsconfig.web.json)
npm run typecheck
```

> `npm run typecheck` checks **only the renderer** (`tsc --noEmit -p tsconfig.web.json`).
> There is no script that covers the main process — run the `tsconfig.node.json` command
> above explicitly to typecheck `src/main/`.

`tsconfig.web.json` is the renderer config. `tsconfig.node.json` is for the Electron main process. They are separate — passing the wrong one gives misleading errors.

## Build

```bash
npx electron-vite build    # full Electron build (run from repo root)
```

## Build artifacts — do not commit

`studio/tsconfig.web.tsbuildinfo` and `studio/tsconfig.node.tsbuildinfo` are incremental build caches. Both are in `.gitignore` — never stage them.

## IPC pattern

Main process exposes handlers via `ipcMain.handle(...)`. Renderer calls them via `window.pathly.*` (contextBridge). When adding a new IPC channel, register it in `src/main/ipc/`, the preload (`src/main/preload/index.ts`), and the type declaration (`src/renderer/src/types/global.d.ts`).

## Terminal IPC — runner mode

`terminal:spawn` accepts an optional `argv` array for non-interactive (runner) mode:

```ts
// Interactive — opens a shell session the user can type into
window.pathly.terminal.spawn(tabId, cwd, 'claude')

// Runner — spawns claude non-interactively; exits when done
window.pathly.terminal.spawn(tabId, cwd, undefined, ['claude', '-p', '...', '--print', '--dangerously-skip-permissions'])
```

On Windows, `terminal.ts` encodes the argv as a base64 PowerShell `-EncodedCommand` to handle newlines, quotes, and other special characters in the prompt safely.

**Runner tab lifecycle:**
1. `terminal:register-runner(tabId, topic, runId, label)` — called before spawn to link the tab to a pipeline run
2. `terminal:spawn(tabId, cwd, undefined, argv)` — spawns the PTY
3. PTY exits → `terminal.ts` POSTs `/runner/terminal/result` automatically (exit code, stdout tail, wall time)

## FSM server lifecycle

On every app launch, `index.ts` ensures a clean FSM server:
1. Check if port 8765 is occupied (`isFsmRunning`)
2. If yes → POST `/shutdown` (graceful, 800ms timeout)
3. Re-check; if still occupied → `forceKillPort` via `netstat -ano` + `taskkill /F` (Windows) or `lsof | kill -9` (macOS/Linux)
4. Start fresh FSM server process

This guarantees the new server always starts, even against old server versions that predate the `/shutdown` endpoint.

## Key Zustand stores

| Store | File | Purpose |
|---|---|---|
| `runnerStore` | `store/runnerStore.ts` | pipeline status, stage, adapter, cost, error — driven by SSE |
| `terminalStore` | `store/terminalStore.ts` | terminal tabs registry; `addTab` registers, `openTab` reveals panel |

`RunnerStatus` union: `'idle' | 'running' | 'paused' | 'blocked' | 'error' | 'done' | 'aborted' | 'finalizing'`

---

## UI coding rules — non-negotiable

### Responsive to container — always

Every component and every button must resize gracefully as its container changes width. Non-negotiable rules:

- **No fixed `width` on containers** — use `width: 100%`, `flex: 1`, or `min-width: 0` instead.
- **Flex children that must shrink need `min-width: 0`** — without it a flex item won't shrink below its content width, causing overflow.
- **Buttons must use `min-width` only as a floor, never a fixed width** — they must be allowed to shrink or wrap.
- **`flex-shrink: 0` is reserved for elements that must never shrink** (icons, single-char badges). Do not apply it to input fields or buttons that contain text.
- **Every panel layout must be verified at ≤200px wide** — use `overflow: hidden` on section containers so nothing escapes the panel bounds.
- **Never use `overflow: visible` on a scroll container** — use `overflow: hidden` or `overflow: auto`.

### No inline styles
Never use `style={{ ... }}` props. All styling goes in the component's `.module.css` file.

**The only accepted exceptions** — values that are genuinely impossible to express in static CSS:
- Dynamic progress bar width: `style={{ width: \`${pct}%\` }}` → use `<progress value={pct} max={100} />` instead (no style prop needed)
- CSS custom properties injected per-element: `style={{ '--anim-delay': `${index * 55}ms` } as React.CSSProperties}` — the value feeds a `var(--anim-delay)` reference in the CSS module; the style prop carries data, not presentation
- Non-standard properties with no TypeScript-safe CSS alternative: `style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}` for Electron drag regions
- Imperative setProperty when the value changes after mount: `ref.current.style.setProperty('--offset', `${y}px`)` inside a `useEffect`

Theme colors and spacing always come from CSS custom properties defined in `tokens.css` (`var(--bg-mantle)`, `var(--accent)`, `var(--text-primary)`, etc.) — never from a `useTheme()` call in JSX.

### Single responsibility — one component, one job
Every component does exactly one thing. If a component needs a comment to explain which "section" it is rendering, it should be a separate component.

**Size guide:**
- Hard limit: ~150 lines per component file
- If a file exceeds this, extract the next logical sub-section into its own file in the same folder

**Folder rule:** each component lives in its own subfolder alongside its CSS module:
```
ComponentName/
  ComponentName.tsx
  ComponentName.module.css
```

**What to extract:**
- A repeated render block → named sub-component in the same folder
- All state + effects + handlers for a large component → a `useComponentName` hook file
- Pure utility functions (no React) → a `utils.ts` or `componentNameUtils.ts` file
- Standalone SVG icons with no CSS → a shared `icons.tsx` file in the feature folder (no subfolder, no `.module.css`); size/color via Lucide `size` prop or `currentColor`, never a `style` prop

**Hook naming and location:**
```
ComponentName/
  hooks/
    useComponentName.ts   ← UI state + event handlers (tab, viewMode, open/close)
    useFeatureName.ts     ← data fetching and side effects (async loads, subscriptions)
```
One hook per concern. UI state hooks return named state + setters + derived handlers. Data hooks return data only — no setters exposed to callers.

### CSS variant pattern — data attributes over class proliferation

When an element has 3+ visual states that differ only in color or decoration, use a `data-*` attribute instead of a cascade of conditional class names. The CSS module handles all variants with attribute selectors:

```tsx
// Instead of: className={`${s.badge} ${isBlocked ? s.blocked : isActive ? s.active : s.idle}`}
<span className={styles.badge} data-status={status}>{label}</span>
```
```css
.badge[data-status='blocked'] { color: var(--red); animation: pulseRed 1.8s infinite; }
.badge[data-status='active']  { color: var(--accent); }
.badge[data-status='idle']    { color: var(--text-muted); }
```

Use `.className` modifiers (`.active`, `.pinned`) for simple binary states. Use `data-*` attributes when there are 3+ mutually exclusive states or when the same element accepts values from an enum/union type.

### Hover state — CSS first, JS only when it must cross a component boundary

| Hover reach | Pattern |
|---|---|
| Affects only the element itself | CSS `:hover` pseudo-class — no JS |
| Shows/hides a child of the same element | CSS `.parent:hover .child { opacity: 1; }` — no JS |
| Shows/hides a sibling in a **different component file** | `const [isHovered, setIsHovered] = useState(false)` in the shared parent → pass as `isHovered: boolean` prop → child applies a CSS class (`.visible`) |

Never put hover state in Zustand. It is ephemeral UI state that belongs to the component that renders the hovered element.

### Buttons
Every `<button>` must have an explicit `type="button"` (or `type="submit"` if it submits a form). No exceptions.

### ARIA
Use `aria-expanded`, `aria-label`, and other ARIA attributes on interactive elements. For dynamic boolean attributes, use the spread pattern to avoid static-analysis false positives:
```tsx
{...(isOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
```

### External links
Any `<a target="_blank">` must include `rel="noopener noreferrer"`.
