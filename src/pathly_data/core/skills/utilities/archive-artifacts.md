# archive-artifacts

This is the canonical, tool-agnostic Pathly behavior for the archive-artifacts skill.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Input contract

- `storage_path` — absolute path to the feature's plan folder (e.g. `pathly/plans/<feature>/`)
- `topic` — feature name string
- `conv` — conversation number (integer)

---

## Step 1 — Collect feedback files

List all `.md` files in `<storage_path>/feedback/`.

If none exist: exit cleanly — no event appended.

---

## Step 2 — Determine next attempt number

Check `pathly/pipeline-walkthrough/<topic>/artifacts/` for existing files.

For each feedback file `<FILENAME>.md`, scan for files matching `<FILENAME>_conv<conv>_attempt<M>.md`.
Set `M` to the highest existing M + 1. If no match exists, M = 1.

---

## Step 3 — Copy files

Create `pathly/pipeline-walkthrough/<topic>/artifacts/` if it does not exist.

For each feedback file `<FILENAME>.md`:
Copy it to `pathly/pipeline-walkthrough/<topic>/artifacts/<FILENAME>_conv<conv>_attempt<M>.md`

---

## Step 4 — Record ACTION_DONE

```bash
pathly-fsm-call record-activity \
  --agent "orchestrator" \
  --feature "<topic>" \
  --summary "archived feedback artifacts for conv <conv>" \
  --project-root "$(pwd)"
```
