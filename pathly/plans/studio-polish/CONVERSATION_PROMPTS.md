---
name: Conversation Guide
---
# studio-polish — Conversation Guide

Split into 4 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: FlowEditor skeleton + FlowWizard save UX + YAML error (Phases 1-4)

**Stories delivered:** S1, S2, S3

**Prompt to paste:**
```
Read pathly/plans/studio-polish/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-polish Conversation 1 (Phases 1-4) from pathly/plans/studio-polish/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read these files in full:
- `studio/src/renderer/src/components/ui/Button.tsx` and `Button.module.css`
- `studio/src/renderer/src/components/FlowEditor/index.tsx`
- `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx`

**Phase 1 — Button loading prop + font fix:**
- Add `loading?: boolean` to the Button props interface
- When `loading === true`: add `disabled` attribute to the button element + add `styles.loading` CSS class
- In Button.module.css: add a CSS spinner via `::after` pseudo-element — 12×12px circle, `border: 2px solid transparent`, `border-top-color: var(--accent)`, `border-radius: 50%`, `animation: spin 0.7s linear infinite`
- Add `@keyframes spin { to { transform: rotate(360deg) } }` to Button.module.css
- Change `font-family: var(--font-family-mono)` in `.btn` to `font-family: var(--font-family-base)`

**Phase 2 — FlowEditor skeleton loader:**
- In `FlowEditor/index.tsx`: when `loading === true` (from `useFlowFile`), render a skeleton component instead of the tab switcher content
- Skeleton: 4 divs with heights `14px`, varying widths (`85%`, `70%`, `90%`, `60%`), `margin-bottom: 10px`, `border-radius: 4px`, `background` using shimmer animation
- Add `@keyframes shimmer` in the component's CSS module (or inline style): background slides from `var(--bg-surface0)` through `var(--bg-surface1)` and back over 1.4s
- The skeleton must be wrapped in the same container as the normal editor content so no layout shift occurs

**Phase 3 — YAML parse error line number:**
- In `useFlowFile.ts`: find the catch block around `jsYaml.load()`
- Check `if (error instanceof jsYaml.YAMLException)` — if true, extract `(error.mark?.line ?? 0) + 1` as the line number
- Set the parse error message to: `` `YAML parse error on line ${line}: ${error.reason ?? error.message}` ``
- If NOT a YAMLException, set to `error.message` as before

**Phase 4 — FlowWizard save button loading state:**
- In `FlowWizard.tsx`: find the Save button (Step 5 / final step)
- Set `loading={saving}` on it — the `saving` state variable already exists
- If the button is a plain `<button>` element, convert it to use the `Button` component with `loading={saving}`

Architectural rules:
- Stay within these 4 files + their CSS modules. Do not change store files, IPC, or Python files.
- The shimmer animation must respect `prefers-reduced-motion` — the existing `--transition-base: 0ms` override in index.html already handles this if you use `var(--transition-base)` for the animation duration. Alternatively, add `@media (prefers-reduced-motion: reduce) { .shimmer { animation: none; } }` in the CSS.

Do NOT touch navigation guard logic, test files, or Python yet.
Verify: `cd studio && npm run build` succeeds without TypeScript errors.
After done, update pathly/plans/studio-polish/PROGRESS.md phases 1-4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Skeleton visible during load; save button spins while saving; YAML errors show line number; buttons use base font.
**Files touched:** `Button.tsx`, `Button.module.css`, `FlowEditor/index.tsx`, `useFlowFile.ts`, `FlowWizard.tsx`

---

## Conversation 2: Unsaved-changes navigation guard (Phase 5)

**Stories delivered:** S4

**Prompt to paste:**
```
Read pathly/plans/studio-polish/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-polish Conversation 2 (Phase 5) from pathly/plans/studio-polish/IMPLEMENTATION_PLAN.md.
Conversation 1 (skeleton, save state, YAML error) must already be complete.

**Before editing anything:** read these files in full:
- `studio/src/renderer/src/components/FlowEditor/index.tsx`
- `studio/src/renderer/src/store/index.ts` (or uiStore.ts — find where `dirtyItems` is managed)
- `studio/src/renderer/src/components/NewItemDialog.tsx` (for dialog pattern reference)

**Phase 5 — Unsaved-changes navigation guard:**
- In `FlowEditor/index.tsx`: add local state `pendingNavigation: SidebarItem | null` (initialized to `null`)
- When the `selectedItem` prop changes (useEffect on `selectedItem`): before switching, check `useUiStore.getState().dirtyItems.has(currentItemPath)` — if the current item is dirty AND the new item is different, set `pendingNavigation` to the new item and return (do NOT switch yet)
- Render a confirm modal when `pendingNavigation !== null`:
  - Title: "Unsaved changes"
  - Body: "You have unsaved changes. Discard and continue?"
  - "Cancel" button: sets `pendingNavigation` to null
  - "Discard changes" button: calls `clearDirty(currentItemPath)`, then allows navigation by triggering the actual item switch (call the parent's item-select handler or update local selection state)
- Follow the same modal pattern as `Sidebar.module.css` `.modalOverlay` / `.modalBox` (use inline styles or a new CSS module — do NOT import Sidebar.module.css into FlowEditor)
- The guard should only activate for flow files (`.flow.yaml`) — check `currentItemPath.endsWith('.flow.yaml')`

Architectural rules:
- The guard lives in FlowEditor, not in the store or sidebar. FlowEditor owns its own dirty-navigation concern.
- Do not modify uiStore or the sidebar item-click handlers.
- Do not implement auto-save — that is out of scope.

Do NOT touch Python files, test files, or Button component.
Verify: `cd studio && npm run build` succeeds.
After done, update pathly/plans/studio-polish/PROGRESS.md phase 5 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Clicking away from a dirty flow shows a confirmation dialog; Cancel keeps the file; Discard navigates.
**Files touched:** `studio/src/renderer/src/components/FlowEditor/index.tsx`

---

## Conversation 3: Vitest suite — useFlowFile + validateFlow (Phases 6-8)

**Stories delivered:** S5

**Prompt to paste:**
```
Read pathly/plans/studio-polish/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-polish Conversation 3 (Phases 6-8) from pathly/plans/studio-polish/IMPLEMENTATION_PLAN.md.
Conversations 1 and 2 must already be complete.

**Before creating test files:** read these source files in full:
- `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
- `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts`
- `studio/package.json` (check existing scripts and devDependencies)

**Phase 6 — Vitest setup:**
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
- Create `studio/src/renderer/src/test-setup.ts`:
  - Mock the Electron preload API so IPC calls don't fail in jsdom:
    ```ts
    import { vi } from 'vitest'
    Object.defineProperty(window, 'api', {
      value: {
        readFile: vi.fn().mockResolvedValue(null),
        writeFile: vi.fn().mockResolvedValue(undefined),
      },
      writable: true,
    })
    ```
  - Adjust the mock shape to match the actual `window.api` interface used in useFlowFile
- Add to `studio/package.json` devDependencies: `"vitest": "^1.0.0"`, `"@vitest/ui": "^1.0.0"`, `"jsdom": "^24.0.0"`, `"@testing-library/react": "^14.0.0"`
- Add to `studio/package.json` scripts: `"test": "vitest run"`

**Phase 7 — useFlowFile tests:**
- Create `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.test.ts`
- Test cases (use `renderHook` from @testing-library/react):
  1. Successful load: mock `readFile` returning valid YAML string → after render, `flowData` is set and `loading` is false
  2. Read error: mock `readFile` rejecting → `loadError` is set, `flowData` is null
  3. YAML parse error: mock `readFile` returning malformed YAML (e.g. `"key: [unterminated"`) → `parseError` contains "line" in the message
  4. Save: call `saveFlow()` (or equivalent save function) → `writeFile` mock is called with the serialized YAML content

**Phase 8 — validateFlow tests:**
- Create `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.test.ts`
- Import `validateFlow` directly (pure function, no hooks needed)
- Test cases:
  1. Valid flow object → returns empty array `[]`
  2. Transition target not in `states` → returns at least one issue with `level: 'error'`
  3. `agent_map` behavior name not in known behaviors list → returns at least one issue with `level: 'warning'`
  4. `transition_rules.default` pointing to a state not declared in transitions → returns an error issue
- Use minimal FlowYaml fixture objects in each test — define them inline in the test file

Architectural rules:
- Tests must not import Electron modules directly — they must go through the `window.api` mock.
- Do not change any source files — only create config and test files.
- If `useFlowFile` uses a different IPC calling convention than expected, read the source carefully and adjust the mock to match.

Do NOT touch Python files, adapter YAMLs, or CSS files.
Verify: `cd studio && npx vitest run` — all tests pass with no pre-existing failures.
After done, update pathly/plans/studio-polish/PROGRESS.md phases 6-8 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** vitest runs; 4 useFlowFile tests pass; 4 validateFlow tests pass.
**Files touched:** `vitest.config.ts`, `test-setup.ts`, `useFlowFile.test.ts`, `validateFlow.test.ts`, `package.json`

---

## Conversation 4: Split setup_command.py (Phase 9)

**Stories delivered:** S6

**Prompt to paste:**
```
Read pathly/plans/studio-polish/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-polish Conversation 4 (Phase 9) from pathly/plans/studio-polish/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read src/install_cli/setup_command.py in full. Map out which functions belong to which layer: CLI/menu vs. orchestration vs. codegen.

**Phase 9 — Split setup_command.py:**

Create `src/install_cli/cli.py`:
- Move `build_parser()` (argparse setup) here
- Move the interactive menu function (the one that prompts the user to select hosts) here
- Move `main()` entry point here — it should call `build_parser()` and then dispatch to `orchestrate.run(args)`
- `cli.py` imports from `orchestrate.py` but NOT vice versa

Create `src/install_cli/orchestrate.py`:
- Move `_run_host()` and `_run_host_uninstall()` here
- Move `ALLOWED_HOSTS` list here
- Move `_codex_agent_toml()`, `_codex_skill_openai_yaml()` here (codex-specific codegen helpers)
- Export a `run(args)` function that dispatches based on `args.command`

Modify `src/install_cli/setup_command.py`:
- Remove all moved code
- Keep only:
  ```python
  from .cli import main
  __all__ = ['main']
  ```
- This makes setup_command.py a thin backward-compatible shim

Update `pyproject.toml` if the `[project.scripts]` entry point references `setup_command:main`:
- If it does, update it to `pathly_adapters.install_cli.cli:main`
- If it already references `install_cli:main` or similar, update accordingly

Architectural rules:
- `cli.py` → `orchestrate.py` → (stitch.py, materialize.py, detect.py, resources.py): dependencies flow one way
- Do not change stitch.py, materialize.py, detect.py, or resources.py
- Do not change any adapter YAML files or studio files
- The public entry point `pathly-setup` must still work after the refactor

Do NOT touch terminal.ts, adapter YAMLs, or test files.
Verify: `python -m pytest tests/ -q` all pass; `python -m pathly_adapters.install_cli --help` prints usage.
After done, update pathly/plans/studio-polish/PROGRESS.md phase 9 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** setup_command.py is ≤20 lines; cli.py and orchestrate.py exist; all tests pass; --help works.
**Files touched:** `src/install_cli/cli.py` (new), `src/install_cli/orchestrate.py` (new), `src/install_cli/setup_command.py`, `pyproject.toml`
