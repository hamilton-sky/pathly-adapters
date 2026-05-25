---
name: Edge Cases
---
# studio-polish — Edge Cases

## Skeleton loader

| Case | Expected behavior |
|---|---|
| File loads in < 100ms | Skeleton flickers briefly then disappears — acceptable |
| File read fails | Skeleton disappears, error banner shown |
| `prefers-reduced-motion` set | Shimmer animation disabled; skeleton is static (no motion) |

## FlowWizard save button

| Case | Expected behavior |
|---|---|
| Save succeeds | Button re-enables after IPC resolves |
| Save fails (IPC error) | Button re-enables; error shown |
| User double-clicks Save | Button disabled after first click; second click is ignored |

## YAML parse error

| Case | Expected behavior |
|---|---|
| js-yaml YAMLException with `mark.line` | "YAML parse error on line N: <reason>" |
| js-yaml throws non-YAMLException | Falls back to `error.message` |
| js-yaml `mark` is undefined | Line display omitted; only the message shown |

## Unsaved-changes guard

| Case | Expected behavior |
|---|---|
| User clicks the SAME file they're already on | No dialog (path unchanged) |
| User clicks a non-.flow.yaml file (markdown) | No guard — markdown editor doesn't use dirty tracking |
| User has a dirty file and closes the Studio window | Electron's `beforeunload` is a separate concern — not in scope for this plan |
| User discards changes then immediately re-opens the same file | File reloads from disk (no dirty flag, no dialog) |

## Tests

| Case | Expected behavior |
|---|---|
| Vitest can't find `window.api` | Test setup file must define it before tests run |
| `useFlowFile` uses a different IPC call name | Builder reads source first, adjusts mock — tests are not rigid about IPC naming |
| `validateFlow` function signature changed | Builder reads source first, adjusts test fixture |
| Pre-existing test failures | Record as baseline before Conversation 3 starts; don't attribute to this feature |

## setup_command.py split

| Case | Expected behavior |
|---|---|
| pyproject.toml entry point still points to `setup_command:main` | Builder updates it; `pathly-setup --help` still works |
| Circular import between cli.py and orchestrate.py | Architectural rule: cli imports orchestrate, not vice versa |
| Test imports `from install_cli.setup_command import main` | Still works via the shim |
