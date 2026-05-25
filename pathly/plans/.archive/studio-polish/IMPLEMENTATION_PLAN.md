---
name: Implementation Plan
---
# studio-polish — Implementation Plan

## Overview
Improves Studio UX in four areas: loading feedback (skeleton + button spinner), safe navigation (unsaved-changes guard), YAML error diagnostics (line numbers), and developer reliability (vitest test suite + installer refactor). All changes are frontend except the final Python refactor.

## Layer Architecture

```
studio/src/renderer/src/
  components/FlowEditor/     ← skeleton, error details, navigation guard
  components/FlowWizard/     ← save button loading state
  components/ui/Button.tsx   ← loading prop + font fix
  store/                     ← dirty-state navigation hook
  vitest.config.ts           ← NEW test runner

src/install_cli/
  cli.py           ← NEW — argparse + menu
  orchestrate.py   ← NEW — _run_host + _run_host_uninstall
  setup_command.py ← MODIFY — thin dispatcher
```

## Prerequisite (pre-flight)
```
cd studio && npx vitest run 2>&1 | head -20   # expect: no config found (that's OK)
cd .. && python -m pytest tests/ -q 2>&1 | head -40
```
Record output as baseline.

## Phases

### Phase 1: Button loading prop + font fix   ← Conversation: 1
**File:** `studio/src/renderer/src/components/ui/Button.tsx`, `studio/src/renderer/src/components/ui/Button.module.css`
**Done when:** `<Button loading>` shows a spinner and is disabled; all buttons use `var(--font-family-base)` not mono.
**Delivers stories:** S2 (partial — Button primitive)
**Depends on:** nothing
**Details:**
- Add `loading?: boolean` prop to the `Button` component interface
- When `loading === true`: add `disabled` attribute + add a `.loading` CSS class
- In `Button.module.css` `.loading::after`: add a CSS keyframe spinner using `border` trick; use `var(--accent)` for the spinning segment; size `12px × 12px`; `animation: spin 0.7s linear infinite`
- Change `font-family: var(--font-family-mono)` in `.btn` to `var(--font-family-base)`

### Phase 2: FlowEditor skeleton loader   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowEditor/index.tsx`
**Done when:** While `loading === true`, 4 shimmer lines are visible in place of the editor content.
**Delivers stories:** S1
**Depends on:** nothing
**Details:**
- When `loading` from `useFlowFile` is true, render a skeleton div instead of the tab content
- Skeleton: 4 `<div>` lines of varying widths (85%, 70%, 90%, 60%), background `var(--bg-surface0)`, `border-radius: 4px`, `height: 14px`, `margin-bottom: 10px`
- Add `@keyframes shimmer` animation: `background: linear-gradient(90deg, var(--bg-surface0) 25%, var(--bg-surface1) 50%, var(--bg-surface0) 75%)` with `background-size: 200% 100%` sliding left→right over 1.4s
- Wrap skeleton in the same container div as the editors so layout does not shift

### Phase 3: YAML parse error line number   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
**Done when:** Switching from YAML tab with a syntax error shows "YAML parse error on line N: <message>" in the error banner.
**Delivers stories:** S3
**Depends on:** nothing
**Details:**
- In the `jsYaml.load()` catch block, check if `error instanceof jsYaml.YAMLException`
- If so, extract `error.mark?.line` (0-indexed) → display as `error.mark.line + 1`
- Store full string: `` `YAML parse error on line ${line}: ${error.reason}` `` into the existing `parseError` state slot
- If not a YAMLException, fall back to `error.message`

### Phase 4: FlowWizard save button loading state   ← Conversation: 1
**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx`
**Done when:** Save button is disabled with spinner while `saving === true`; returns to normal on completion.
**Delivers stories:** S2
**Depends on:** Phase 1 (Button loading prop)
**Details:**
- Import the updated `Button` component (or use the existing save button element)
- Set `loading={saving}` on the Save button
- The `saving` state variable already exists in FlowWizard — just wire it up
- Do NOT change the save logic itself

### Phase 5: Unsaved-changes navigation guard   ← Conversation: 2
**File:** `studio/src/renderer/src/components/FlowEditor/index.tsx`, `studio/src/renderer/src/store/index.ts`
**Done when:** Clicking a different sidebar item while `dirty` is true shows a confirm dialog; Cancel keeps current file open; Discard navigates.
**Delivers stories:** S4
**Depends on:** Phase 1-4 done (Conv 1 complete)
**Details:**
- In `FlowEditor/index.tsx`: check if the `selectedItem` prop is about to change AND `isDirty(currentPath)` is true
- Use a local state `pendingNavigation: SidebarItem | null` — when set, show the confirm dialog
- Confirm dialog: use the existing `modalOverlay`/`modalBox` pattern from `Sidebar.module.css` or the `NewItemDialog` component as a reference; render inline in FlowEditor
- Dialog buttons: "Cancel" (sets `pendingNavigation` to null) and "Discard changes" (clears dirty, proceeds to the pending item)
- The `isDirty` check uses `useUiStore.getState().dirtyItems.has(path)` (already available)
- Do NOT save on discard — only clear the dirty flag and navigate

### Phase 6: Vitest setup   ← Conversation: 3
**File:** `studio/vitest.config.ts`, `studio/package.json`
**Done when:** `cd studio && npx vitest run` finds and runs test files.
**Delivers stories:** S5 (partial)
**Depends on:** Phase 1-5 done
**Details:**
- Create `studio/vitest.config.ts`:
  ```ts
  import { defineConfig } from 'vitest/config'
  export default defineConfig({
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/renderer/src/test-setup.ts'],
    },
  })
  ```
- Create `studio/src/renderer/src/test-setup.ts` — mock Electron IPC: `vi.mock('../../preload/index', () => ({ api: { readFile: vi.fn(), writeFile: vi.fn() } }))`
- Add `"test": "vitest run"` to `studio/package.json` scripts if not present
- Add `vitest`, `@vitest/ui`, `jsdom` to `devDependencies` in `studio/package.json`

### Phase 7: useFlowFile tests   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.test.ts`
**Done when:** Tests for load success, load error, YAML parse error, and save all pass.
**Delivers stories:** S5
**Depends on:** Phase 6
**Details:**
- Test: loading a valid YAML file → `flowData` is set, `loading` is false
- Test: readFile IPC rejects → `loadError` is set, `flowData` is null
- Test: readFile returns malformed YAML → `parseError` contains "line N" string
- Test: `saveFlow()` called with valid data → `writeFile` IPC is called with serialized YAML

### Phase 8: validateFlow tests   ← Conversation: 3
**File:** `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.test.ts`
**Done when:** Tests for valid flow, missing transition target, and unknown behavior all pass.
**Delivers stories:** S5
**Depends on:** Phase 6
**Details:**
- Test: valid `FlowYaml` object → `validateFlow()` returns empty array
- Test: transition target not in `states` → returns issue with level `error`
- Test: `agent_map` behavior name not in known library → returns issue with level `warning`
- Test: `transition_rules.default` pointing to undeclared transition target → returns issue

### Phase 9: Split setup_command.py   ← Conversation: 4
**File:** `src/install_cli/cli.py` (CREATE), `src/install_cli/orchestrate.py` (CREATE), `src/install_cli/setup_command.py` (MODIFY)
**Done when:** `python -m pathly_adapters.install_cli --help` works; existing pytest suite passes; `setup_command.py` is ≤80 lines.
**Delivers stories:** S6
**Depends on:** nothing (independent Python work)
**Details:**
- Create `cli.py`: move `build_parser()`, interactive menu function, and `main()` entry point here
- Create `orchestrate.py`: move `_run_host()`, `_run_host_uninstall()`, and the `ALLOWED_HOSTS` list here; also move `_codex_agent_toml()`, `_codex_skill_openai_yaml()` (codex-specific codegen) into `orchestrate.py` for now
- `setup_command.py`: keep only `from .cli import main` and a `__all__` — becomes the thin public entry point
- Update `pyproject.toml` entry point if it references `setup_command:main` → point to `cli:main`
**Verify:** `python -m pytest tests/ -q` all pass

## Key Decisions
- Skeleton uses CSS animation only (no JS timers) — respects `prefers-reduced-motion` via existing `--transition-base: 0ms` override
- Navigation guard uses local state pattern (not store) — the guard is FlowEditor's concern, not global state
- Vitest jsdom environment — matches renderer code that uses DOM APIs; node environment would require more mocking
