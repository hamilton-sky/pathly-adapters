# end

This is the canonical, tool-agnostic Pathly behavior for the end skill.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Adapter Surface

This core prompt names Pathly workflows, not host commands. Adapters translate
those workflow routes into their native surface.

---

You are wrapping up the current session.

## Step 1 — Find in-progress feature

Scan `plans/` (skip `.archive/`). For each feature folder, read `PROGRESS.md` if present.
Look for a feature whose `PROGRESS.md` contains `status: IN PROGRESS` or `Status: IN PROGRESS`.

## Step 2 — If a feature is in progress

Print a completion summary:

```
Feature: <feature-name>
Conversations done / total: <X> / <Y>
```

Ask:

```
Write a retro? (y/n):
```

- **y**: route to `retro <feature>`
- **n**: print:
  ```
  All done. Changes committed? Run git commit if not.
  ```

## Step 3 — If no feature is in progress

Print:

```
Nothing in progress. All done.
```
