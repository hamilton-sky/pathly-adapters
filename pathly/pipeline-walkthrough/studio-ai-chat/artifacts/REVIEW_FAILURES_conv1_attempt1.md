# Review Failures — studio-ai-chat Conv 1

## Conversation
Conv 1 — added GET /status route to src/pathly_orchestrator/http_server.py

---

## Violations

### VIOLATION-1 — Path traversal: missing containment check on `project_root`

**File:** `src/pathly_orchestrator/http_server.py`, lines 205–224
**Rule:** Security — transport boundary must validate all user-supplied paths before filesystem access
**Description:** `/status` accepts `project_root` as a query parameter (line 205), constructs `plans_dir = Path(project_root) / "pathly" / "plans"` (line 212) without calling `.resolve()`, and then globs and reads STATE.json files (lines 220–224) without checking that the resulting paths are contained within the resolved root. An attacker-supplied value such as `../../etc` can escape the intended boundary and cause the endpoint to read STATE.json files anywhere on the filesystem.

**Established pattern (must match):**
The `/events/stream` endpoint at lines 580–585 applies the correct guard:
```python
resolved_root = Path(project_root).resolve()
target_path = (resolved_root / "pathly" / "plans" / topic / "EVENTS.jsonl").resolve()
if not target_path.is_relative_to(resolved_root):
    return jsonify({"error": "Invalid project_root"}), 400
```

The `/status` endpoint must apply the same `.resolve()` + `.is_relative_to()` containment check to `plans_dir` before globbing, and must also verify that each `state_file` resolved path is relative to `resolved_root` before passing it to `read_state`.

---

## Warnings (non-blocking)

None for this diff.

---

## Pass

- Layer contract: `/status` correctly delegates state reads to `read_state()` (business logic layer) rather than re-implementing FSM logic inline. Transport boundary responsibility is respected in all respects except the path guard noted above.
- No hardcoded credentials or secrets introduced.
- No new imports from layers above `http_server.py`.
