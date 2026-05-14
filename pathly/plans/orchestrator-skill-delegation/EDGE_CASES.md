# orchestrator-skill-delegation — Edge Cases

## Category 1: Commit guard conditions

### EC-1.1: Active feedback file present when commit is triggered
- **Trigger**: A `REVIEW_FAILURES.md` or similar feedback file exists in `<storage_path>/feedback/` when the orchestrator hits a transition with `skill: commit`
- **Current behavior**: Orchestrator's inline logic would skip the commit and log suppression
- **Expected behavior**: `commit` skill detects the feedback file, prints "commit suppressed — active feedback file: REVIEW_FAILURES.md", exits without committing
- **Handled in**: Phase 1 — commit skill guard

### EC-1.2: Clean working tree (nothing to commit)
- **Trigger**: Subagent ran but made no file changes; `git add -A && git commit` exits with "nothing to commit"
- **Expected behavior**: Skill exits cleanly, still appends ACTION_DONE, does not error
- **Handled in**: Phase 1 — commit skill handles non-zero git exit code on clean tree

---

## Category 2: archive-artifacts edge cases

### EC-2.1: No feedback files to archive
- **Trigger**: `archive-artifacts` skill is spawned but `<storage_path>/feedback/` is empty
- **Expected behavior**: Skill exits cleanly (no-op), appends ACTION_DONE
- **Handled in**: Phase 3

### EC-2.2: Same feedback file archived multiple times (multiple review cycles)
- **Trigger**: `REVIEW_FAILURES.md` is written, archived (attempt 1), deleted, written again, archived (attempt 2)
- **Expected behavior**: Second archive creates `REVIEW_FAILURES_conv2_attempt2.md` — not overwriting attempt 1
- **Handled in**: Phase 3 — M is derived from highest existing file with same name prefix

---

## Category 3: Installed vs source sync

### EC-3.1: Orchestrator updated in source but not installed
- **Trigger**: Conv 2 edits source `orchestrator.md` but Phase 6 is skipped or fails
- **Expected behavior**: Pipeline uses old inline logic — old `type:` keys still work. Builder must sync Phase 6 before closing Conv 2.
- **Handled in**: Phase 6 — explicit sync step with diff verify

### EC-3.2: Flow YAML updated to `skill:` but orchestrator still uses `type:` dispatch
- **Trigger**: Conv 3 runs before Conv 2 is complete
- **Expected behavior**: Orchestrator encounters unknown `skill:` key, halts and reports "unknown transition action type"
- **Mitigation**: CONVERSATION_PROMPTS.md Conv 3 requires checking Conv 2 is DONE in PROGRESS.md before proceeding

---

## Known Limitations
- `update_progress` action type is removed from orchestrator spec but no replacement skill is created in this plan — flows that previously used it will fail silently (no-op). Acceptable because no current flow uses it.
