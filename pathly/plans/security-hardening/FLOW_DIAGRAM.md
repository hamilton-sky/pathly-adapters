---
name: Flow Diagram
---
# security-hardening — Flow Diagram

## Terminal spawn (hardened)

```
Renderer                     Main: terminal.ts
   │                               │
   │── terminal:spawn ────────────►│
   │   {tabId, cwd, command?}      │
   │                          command in ALLOWED_SHELLS?
   │                          NO ──► terminal:error ──► Renderer
   │                          YES
   │                          isValidProjectPath(cwd)?
   │                          NO ──► terminal:error ──► Renderer
   │                          YES
   │                          node-pty.spawn(shell, [], {cwd})
   │                          ptyOwners.set(tabId, sender.id)
   │◄── terminal:data ────────────│  (PTY output flows back)
   │
   │── terminal:write ───────────►│
   │   {tabId, data}              │
   │                          ptyOwners.get(tabId) === sender.id?
   │                          NO ──► return (silent)
   │                          YES
   │                          pty.write(data)
```

## Telemetry write path

```
record(event)
   │
   ├── PATHLY_FF_TELEMETRY == '0' ? ──► return
   │
   ├── activity.jsonl > 5MB ? ──► rename to activity.jsonl.bak
   │                               open fresh activity.jsonl
   │
   └── append JSON line
```

## Manifest load (hardened)

```
_load_manifest(dest)
   │
   ├── read .pathly-manifest.json
   │     ├── missing / OSError ──► return {}
   │     └── JSONDecodeError  ──► return {}
   │
   ├── _hash_files_dict(files)
   │     └── mismatch ──► ValueError
   │                        │
   │                   except ValueError
   │                        │
   │                   raise RuntimeError(
   │                     "Manifest integrity check failed..."
   │                   )
   │                        │
   │                   caller prints + exits 1
   │
   └── match ──► return manifest dict
```
