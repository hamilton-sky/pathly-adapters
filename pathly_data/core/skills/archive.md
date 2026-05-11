# archive

This is the canonical, tool-agnostic Pathly behavior for the archive workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Step 1: Validate

If `$ARGUMENTS` is empty: stop →
```
Route: `archive <feature-name>`
Example route: `archive hotel-search`
```

Set `FEATURE = $ARGUMENTS`.

Check `plans/$FEATURE/` exists. If not: stop →
```
plans/$FEATURE/ not found. Nothing to archive.
```

Check `plans/$FEATURE/RETRO.md` exists. If not: stop →
```
RETRO.md missing. Run route `retro $FEATURE` before archiving.
The retro seed is needed for future storm sessions.
```

Read `plans/$FEATURE/PROGRESS.md`. Check all conversations are DONE.
If any TODO: stop →
```
$FEATURE has incomplete conversations. Finish building before archiving.
Incomplete: [list the TODO conversations]
```

Check `plans/$FEATURE/feedback/` — any open feedback files? If yes: stop →
```
Open feedback files found: [list them]
Resolve all feedback before archiving.
```

---

## Step 2: Archive

Create `plans/.archive/` if it does not exist.

Move `plans/$FEATURE/` → `plans/.archive/$FEATURE/`

Use the host's shell tool:
```bash
mv plans/$FEATURE plans/.archive/$FEATURE
```

---

## Step 3: Report

```
Archived: $FEATURE

  From: plans/$FEATURE/
  To:   plans/.archive/$FEATURE/

  Recoverable: git checkout plans/$FEATURE/
  RETRO.md seed: plans/.archive/$FEATURE/RETRO.md

plans/ is now clean.
```

If `plans/` now has no remaining active features, add:
```
No active features remaining. Start the next one with:
  team-flow <new-feature>
```
