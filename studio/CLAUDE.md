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

# Both (npm script)
npm run typecheck
```

`tsconfig.web.json` is the renderer config. `tsconfig.node.json` is for the Electron main process. They are separate — passing the wrong one gives misleading errors.

## Build

```bash
npx electron-vite build    # full Electron build (run from repo root)
```

## Build artifacts — do not commit

`studio/tsconfig.web.tsbuildinfo` and `studio/tsconfig.node.tsbuildinfo` are incremental build caches. Both are in `.gitignore` — never stage them.

## IPC pattern

Main process exposes handlers via `ipcMain.handle(...)`. Renderer calls them via `window.api.*` (contextBridge). When adding a new IPC channel, register it in both `src/main/` and the preload script.

---

## UI coding rules — non-negotiable

### No inline styles
Never use `style={{ ... }}` props. All styling goes in the component's `.module.css` file.

**The only accepted exceptions** — values that are genuinely impossible to express in static CSS:
- Dynamic progress bar width: `style={{ width: \`${pct}%\` }}` → use `<progress value={pct} max={100} />` instead (no style prop needed)
- CSS custom properties set imperatively via `ref.current.style.setProperty(...)` in a `useEffect` — this bypasses the JSX style prop entirely

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

### Buttons
Every `<button>` must have an explicit `type="button"` (or `type="submit"` if it submits a form). No exceptions.

### ARIA
Use `aria-expanded`, `aria-label`, and other ARIA attributes on interactive elements. For dynamic boolean attributes, use the spread pattern to avoid static-analysis false positives:
```tsx
{...(isOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
```

### External links
Any `<a target="_blank">` must include `rel="noopener noreferrer"`.
