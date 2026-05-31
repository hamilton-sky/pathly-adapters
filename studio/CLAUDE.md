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
