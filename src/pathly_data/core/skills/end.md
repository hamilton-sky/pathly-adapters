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

1. Invoke the `fsm-call` skill with:
   ```json
   {"action":"next_action","flow":"<flow>","topic":"<topic>","project_root":"<cwd>"}
   ```

2. Print the read-only summary panel using data from the next_action response.
   Check whether any `*.md` files exist in `plans/<feature>/feedback/`:

```
─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  <If any *.md file exists in feedback/:>
  ! Open feedback — resolve before archiving.
─────────────────────────────────────────────────────────
  Conversations completed: <N>
─────────────────────────────────────────────────────────
```

3. Then ask:

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
