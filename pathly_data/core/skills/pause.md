# pause

This is the canonical, tool-agnostic Pathly behavior for the pause skill.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Adapter Surface

This core prompt names Pathly workflows, not host commands. Adapters translate
those workflow routes into their native surface.

---

Pause the current session cleanly without losing state.

## Step 1 — Find in-progress feature

Scan `plans/` (skip `.archive/`). For each feature folder, read `PROGRESS.md` if present.
Look for a feature whose `PROGRESS.md` contains `status: IN PROGRESS` or `Status: IN PROGRESS`.

## Step 2 — If a feature is in progress

Write `status: PAUSED` to that feature's `PROGRESS.md`.

Print:

```
Session paused.
Feature: <feature-name>
Conversations done / total: <X> / <Y>

Resume with:  /pathly go
Consult a role: /pathly meet
```

## Step 3 — If no feature is in progress

Print:

```
Nothing in progress. Session closed.

Start fresh with: /pathly start
```
