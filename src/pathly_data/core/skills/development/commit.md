# commit

This is the canonical, tool-agnostic Pathly behavior for the commit skill.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Input contract

- `message` — commit message string
- `storage_path` — absolute path to the feature's plan folder (e.g. `pathly/plans/<feature>/`)
- `topic` — feature name string

---

## Step 1 — Guard: check for open feedback files

List all `.md` files in `<storage_path>/feedback/`.

If any exist:
```
commit suppressed — active feedback file: <name>
```
Exit without committing.

---

## Step 2 — Stage all changes

Run:
```bash
git add -A
```

---

## Step 3 — Commit

Run:
```bash
git commit -m "<message>"
```

If git exits with code 1 and the output contains "nothing to commit": exit cleanly — no event appended.

---

## Step 4 — Append ACTION_DONE event

Append this JSON line to `<storage_path>/EVENTS.jsonl`:
```json
{"type": "ACTION_DONE", "action": "commit", "topic": "<topic>", "ts": "<iso-timestamp>"}
```
