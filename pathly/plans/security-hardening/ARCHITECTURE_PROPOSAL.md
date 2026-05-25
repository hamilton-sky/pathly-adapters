---
name: Architecture Proposal
---
# security-hardening — Architecture Proposal

## IPC Trust Boundary

```
Renderer (untrusted)                Main Process (trusted)
─────────────────────               ─────────────────────────────
terminal:spawn(tabId,               ALLOWED_SHELLS allowlist check
  cwd, command?)        ──────────► isValidProjectPath(cwd) check
                                    ptyOwners.set(tabId, sender.id)
                                    node-pty.spawn()

terminal:write(tabId, data) ──────► ptyOwners.get(tabId) === sender.id?
                                    YES → pty.write(data)
                                    NO  → silent return
```

**Design rule:** The main process never trusts any string from the renderer as an executable path or shell argument. Shell selection is allowlist-only; CWD is bounds-checked; write ownership is enforced at the tabId level.

## Telemetry Opt-Out

```
storage.record(event)
  │
  ├─ PATHLY_FF_TELEMETRY == '0' ? → return (no write)
  │
  ├─ activity.jsonl > 5 MB ? → rotate (rename to .bak, open fresh)
  │
  └─ append JSON line to activity.jsonl
```

**Why env var, not config file:** The `.env.example` already documents `PATHLY_FF_TELEMETRY=1` as the canonical knob. Using `os.environ.get()` keeps the check zero-dependency and works in CI.

## Manifest Integrity Error Chain

```
_load_manifest(dest)
  │
  ├─ json.JSONDecodeError → return empty manifest (existing behavior)
  ├─ OSError              → return empty manifest (existing behavior)
  └─ _hash_files_dict() mismatch
       │
       ├─ OLD: ValueError propagates unhandled → crash with traceback
       └─ NEW: except ValueError → raise RuntimeError(clear message)
                                   caller prints + exits non-zero
```

**Why RuntimeError, not SystemExit:** `RuntimeError` is catchable by test code and by callers who want to handle it programmatically. `SystemExit` would make unit testing harder.
