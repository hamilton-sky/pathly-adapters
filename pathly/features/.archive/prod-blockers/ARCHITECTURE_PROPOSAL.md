# prod-blockers — Architecture Proposal

## Problem Statement

Seven production-blocking issues span two subsystems: the HTTP orchestrator server (`http_server.py`, `fsm.py`) and the install CLI (`materialize.py`). The issues fall into three categories: information disclosure (traceback leak), reliability gaps (deprecated API, missing timeouts, orphaned threads), and security exposure (path traversal, manifest integrity). Each fix is surgical — no new abstractions are introduced, no existing interfaces are broken.

## Proposed Solution

Apply targeted, minimal changes to three existing files in two conversations of core fixes, one test conversation, with a manifest integrity conversation in between. All changes stay within the existing module boundaries and layer responsibilities.

## Layer Breakdown

```
HTTP API layer    (src/pathly_orchestrator/http_server.py)
     │  Conv 1: remove traceback leak from 500 handlers
     │  Conv 3: resolve project_root; stop orphaned tailer threads
     ▼
Orchestration layer   (src/pathly_orchestrator/fsm.py)
     │  Conv 1: fix deprecated datetime; add subprocess timeouts
     ▼
Install CLI layer     (src/install_cli/materialize.py)
     │  Conv 2: add manifest version + hash on write; validate on load; guard uninstall
     ▼
Test layer            (tests/)
          Conv 4: test_rollback.py, test_manifests.py
```

## Key Design Decisions

### Decision 1: Log-then-strip for 500 error responses

- **Options considered**: (A) strip traceback only, (B) strip traceback and log to stderr via logging, (C) add a configurable debug mode that re-enables tracebacks.
- **Chosen**: B
- **Rationale**: Stripping without logging loses diagnosability. A debug mode adds scope and config surface that is out of bounds for a security fix. `logging.exception()` writes to stderr without any config changes and integrates with existing Python logging infrastructure.

### Decision 2: SHA-256 over the `files` sub-dict only

- **Options considered**: (A) hash the entire manifest JSON, (B) hash only the `files` sub-dict, (C) use a Merkle tree per-file.
- **Chosen**: B
- **Rationale**: Hashing the full manifest would include the hash field itself, creating a circular dependency. Hashing only `files` is the canonical content; `_manifest_version` and `_manifest_hash` are metadata. A Merkle tree is disproportionate to the scale of the manifest.

### Decision 3: Raise ValueError on manifest integrity failure (not silent fallback)

- **Options considered**: (A) raise ValueError, (B) log warning and return empty manifest, (C) return the manifest as-is with a warning flag.
- **Chosen**: A
- **Rationale**: The existing silent fallback to `{"files": {}}` is the root cause of the integrity gap. Silent degradation on tampered manifests is worse than a hard failure. The caller can choose to handle `ValueError` and decide whether to re-install.

### Decision 4: `.resolve()` + `.is_relative_to()` for path traversal guard

- **Options considered**: (A) check for `..` in raw string, (B) resolve both paths and use `.is_relative_to()`, (C) allowlist of valid project_root prefixes.
- **Chosen**: B
- **Rationale**: String-based `..` checks are bypassable via encoded or symlinked paths. `.resolve()` follows symlinks and normalizes the path. An allowlist requires configuration that does not exist. `Path.is_relative_to()` is the idiomatic Python 3.9+ approach and is unambiguous.

### Decision 5: Threading lock for SSE cleanup

- **Options considered**: (A) check if a lock exists and reuse it, (B) always add a new lock, (C) use `collections.defaultdict` with atomic operations.
- **Chosen**: A
- **Rationale**: Adding a duplicate lock is a bug. `collections.defaultdict` does not eliminate race conditions on the check-then-act pattern. The builder must inspect the file first and reuse any existing lock.

## Key Components

- `_hash_files_dict(files: dict) -> str` — new helper in `materialize.py`; computes canonical SHA-256 of the files dict.
- `_lock` — threading lock in `http_server.py` (added only if not already present); guards `_clients` and `_tailers` mutations in the SSE cleanup path.

## Interface Design

No public interfaces change. All modifications are internal to existing functions. The only new public-facing behavior is:
- `/events/stream` now returns HTTP 400 for invalid `project_root` values.
- `uninstall()` accepts a new `confirm_manifest: bool = False` keyword argument.
- `_load_manifest()` may now raise `ValueError` (previously only raised implicitly).

## Risks

- **`Path.is_relative_to()` is Python 3.9+**: If the project targets Python 3.8, use `str(events_path).startswith(str(resolved_root))` as a fallback. Builder must check the Python version constraint before using `is_relative_to`.
- **Manifest hash breaks existing installs**: Any manifest written before this change will fail the version check. Builder must document a migration path or add a one-time migration flag if existing installs are in scope.
- **SSE lock contention**: Adding a lock to the SSE finally block introduces a potential bottleneck under high client churn. Acceptable given the expected concurrency level.
