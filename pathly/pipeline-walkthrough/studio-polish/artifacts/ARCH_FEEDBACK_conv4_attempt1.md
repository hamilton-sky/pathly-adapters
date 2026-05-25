---
type: arch-feedback
feature: studio-polish
conversation: 4
reviewer: reviewer
---

# Architectural Feedback — studio-polish Conv 4

## Violations

### VIOLATION-1 — setup_command.py exceeds thin-shim contract

**File:** `src/install_cli/setup_command.py` (89 lines)
**Rule:** ARCHITECTURE_PROPOSAL.md — installer module dependency graph:
> `setup_command.py` ← shim: `from .cli import main; __all__ = ['main']`

**Description:** `setup_command.py` contains the full `main()` function with argparse setup, host validation, and dispatch logic (lines 12–88). It is 89 lines. The contract requires it to be a thin shim of at most 2 meaningful lines — one import re-export and an `__all__` declaration.

**Evidence:**
- Line 1–7: `import argparse`, `import importlib.metadata`, `import sys`, plus imports from `.detect`, `.orchestrate`, `.cli`
- Lines 12–88: full `main()` implementation with argparse, host validation loop, uninstall dispatch, and apply dispatch
- `cli.py` does NOT define `main()` — it defines only `_interactive_menu()` and `_uninstall_package()`

**Required state per contract:**
```python
from .cli import main
__all__ = ['main']
```

**Actual state:** `cli.py` is missing `main()`. The executor must move `main()` from `setup_command.py` to `cli.py`, then reduce `setup_command.py` to the 2-line shim above.

---

## No dependency direction violations

- `orchestrate.py` does NOT import from `cli.py` — dependency direction is correct.
- `cli.py` imports only from `.orchestrate` — no reverse import.
- `__main__.py` imports from `.setup_command` — entry point chain is intact.
- No circular dependencies detected.

---

## Summary

One blocking architectural violation: `main()` was never moved to `cli.py`. The thin-shim requirement for `setup_command.py` is unmet. This must be resolved before Conv 4 is marked complete.
