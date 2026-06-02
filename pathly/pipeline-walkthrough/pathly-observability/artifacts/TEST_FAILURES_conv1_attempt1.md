## TEST_FAILURES — pathly-observability

### [FAIL] S-06: Phase-boundary logging in plan.md + new log-phase utility

- Criterion: `grep "log-phase" src/pathly_data/core/skills/development/plan.md` returns at least 2 matches
- Evidence: `src/pathly_data/core/skills/development/plan.md` does not exist. The file is at `src/pathly_data/core/skills/planning/plan.md`, which contains 6 `log-phase` calls. The acceptance criterion references the wrong directory (`development/` instead of `planning/`).
- Fix: Update the acceptance criterion grep path to `src/pathly_data/core/skills/planning/plan.md`, OR move/symlink the file to match the criterion. The underlying behavior (log-phase calls in plan.md) is fully implemented.

---

### [FAIL] S-07: Three-phase structure in design.md and storm.md

- Criterion: `grep -n "phase: analyze" src/pathly_data/core/skills/development/design.md src/pathly_data/core/skills/development/storm.md` returns at least 2 matches
- Evidence: Two issues:
  1. `src/pathly_data/core/skills/development/storm.md` does not exist. storm.md is located at `src/pathly_data/core/skills/planning/storm.md`.
  2. The grep pattern `phase: analyze` (lowercase p) returns 0 matches. Both files use `## Phase: analyze` (capital P). The pattern would need to be `Phase: analyze` or use `-i` flag.
  Running the exact grep from the criterion returns exit code 2 (file not found) with 0 matches.
  The underlying behavior IS implemented: both design.md (line 6) and planning/storm.md (line 6) contain `## Phase: analyze` sections, and both call `log-phase PHASE_START analyze` and `log-phase PHASE_DONE analyze`.
- Fix: Correct the criterion's grep command to use the right path (`planning/storm.md`) and either (a) use `-i` flag for case-insensitive matching, or (b) change the pattern to `Phase: analyze` to match the actual heading format used in both files.
