# archive

This is the canonical, tool-agnostic Pathly behavior for the archive workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Feature detection

If `$ARGUMENTS` contains a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `pathly/features/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/features/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/features/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

## Step 1: Validate

Set `FEATURE` from the Feature detection above.

Check `pathly/features/$FEATURE/` exists. If not: stop →
```
pathly/features/$FEATURE/ not found. Nothing to archive.
```

Check `pathly/features/$FEATURE/RETRO.md` exists. If not: stop →
```
RETRO.md missing. Run route `retro $FEATURE` before archiving.
The retro seed is needed for future storm sessions.
```

Read `pathly/features/$FEATURE/PROGRESS.md`. Check all conversations are DONE.
If any TODO: stop →
```
$FEATURE has incomplete conversations. Finish building before archiving.
Incomplete: [list the TODO conversations]
```

Check `pathly/features/$FEATURE/feedback/` — any open feedback files? If yes: stop →
```
Open feedback files found: [list them]
Resolve all feedback before archiving.
```

---

## Step 2: Archive

Create `pathly/features/.archive/` if it does not exist.

Move `pathly/features/$FEATURE/` → `pathly/features/.archive/$FEATURE/`

Use the host's shell tool:
```bash
mv pathly/features/$FEATURE pathly/features/.archive/$FEATURE
```

---

## Step 2b — Auto-promote lessons

Before reporting, check for and promote any candidate lessons:

1. Check if `LESSONS_CANDIDATE.md` exists at the project root.
2. If it exists and is non-empty, automatically invoke the `lessons` skill.
3. This updates `LESSONS.md` with patterns from this and previous features.
4. If `LESSONS_CANDIDATE.md` does not exist or is empty, skip silently.

---

## Step 3: Report

```
Archived: $FEATURE

  From: pathly/features/$FEATURE/
  To:   pathly/features/.archive/$FEATURE/

  Recoverable: git checkout pathly/features/$FEATURE/
  RETRO.md seed: pathly/features/.archive/$FEATURE/RETRO.md

pathly/features/ is now clean.
```

If `pathly/features/` now has no remaining active features, add:
```
No active features remaining. Start the next one with:
  team <new-feature>
```
