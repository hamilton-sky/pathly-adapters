# prod-blockers — Flow Diagram

## SSE Thread Lifecycle (Happy Path: connect → stream → disconnect)

```
Client connects to /events/stream?project_root=<P>&topic=<T>
        │
        ▼
Resolve project_root → resolved_root
        │
        ▼
Construct events_path = resolved_root / pathly/plans/<T>/EVENTS.jsonl
        │
        ├─ events_path not relative to resolved_root ──► HTTP 400 (Invalid project_root)
        │
        ▼
key = (resolved_root, topic)
        │
        ├─ key not in _tailers ──► start _tail_events thread; store stop_evt in _tailers[key]
        │
        ▼
Append client_q to _clients[key]
        │
        ▼
generate() yields SSE events from client_q
        │
        ▼
Client disconnects (GeneratorExit / connection drop)
        │
        ▼
finally: remove client_q from _clients[key]
        │
        ├─ _clients[key] not empty ──► done (other clients still connected)
        │
        ▼
_clients[key] is empty
        │
        ▼
acquire _lock
  pop stop_evt from _tailers[key]
  stop_evt.set()          ──► tailer thread receives signal and exits
  del _clients[key]
release _lock
```

## Path Traversal Rejection Flow

```
/events/stream request with project_root=../../etc
        │
        ▼
Path("../../etc").resolve() → /etc  (absolute, symlinks followed)
        │
        ▼
events_path = Path("/etc/pathly/plans/<T>/EVENTS.jsonl").resolve()
        │
        ▼
events_path.is_relative_to(resolved_root)?
        │
        └─ False ──► return jsonify({"error": "Invalid project_root"}), 400
```

## Manifest Write / Read Integrity Flow

```
_save_manifest(manifest)
        │
        ▼
manifest["_manifest_version"] = "1"
manifest["_manifest_hash"] = SHA-256(canonical JSON of manifest["files"])
        │
        ▼
write JSON to disk

── later ──

_load_manifest()
        │
        ├─ FileNotFoundError or json.JSONDecodeError ──► return {"files": {}}  (existing fallback)
        │
        ▼
data loaded from disk
        │
        ├─ "_manifest_version" not in data ──► raise ValueError("Manifest missing _manifest_version field")
        │
        ▼
recomputed = SHA-256(canonical JSON of data["files"])
        │
        ├─ recomputed != data["_manifest_hash"] ──► raise ValueError("Manifest hash mismatch — ...")
        │
        ▼
return data  (trusted)
```

## 500 Error Response Flow (after fix)

```
POST /next_action  (or /complete_stage)
        │
        ▼
handler logic raises Exception
        │
        ▼
except Exception as e:
  logging.exception("...")   ──► full traceback written to stderr
        │
        ▼
return jsonify({"error": str(e), "type": type(e).__name__}), 500
        │
        └─ no "traceback" key in response body
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `_tail_events` | Background thread that reads EVENTS.jsonl and pushes lines to all client queues for a given key |
| `_tailers` | Module-level dict mapping `(project_root, topic)` to the tailer thread's stop event |
| `_clients` | Module-level dict mapping `(project_root, topic)` to a list of per-client queues |
| `stop_evt` | `threading.Event` — set to signal the tailer thread to exit its read loop |
| `_lock` | `threading.Lock` — guards mutations to `_clients` and `_tailers` in the disconnect path |
| `_hash_files_dict` | Helper in `materialize.py` — computes canonical SHA-256 of the `files` sub-dict |
