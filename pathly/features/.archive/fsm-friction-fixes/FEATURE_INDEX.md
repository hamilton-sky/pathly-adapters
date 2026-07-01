# FEATURE_INDEX — fsm-friction-fixes

**What this feature is:** Three independent reliability fixes to the Pathly FSM pipeline — server auto-start, scope gate accuracy, and multi-conversation routing.

**What it fixes:** (1) "FSM server unavailable" errors caused by a fixed 2 s sleep and a broken PowerShell fallback in `fsm-call.md`; (2) SCOPE_VIOLATION false positives caused by diffing against a SHA instead of tracking what the builder actually touched; (3) silent FSM advancement past unfinished work when a reviewer forgets to write `MORE_CONVS_NEEDED.md`.

**What it does not touch:** Studio/Electron UI, CLI flag surface, OS-level service registration, and any auto-migration of legacy STATE.json files.
