# Retro — g1-feature-planner-decompose

**Feature:** planner-hierarchy  
**Goal:** g1-feature-planner-decompose-2672c936  
**Date:** 2026-07-06  
**Pipeline:** BUILD → REVIEW (failed) → BUILD (fix) → REVIEW (pass) → TEST (pass) → RETRO

---

## 1. What went well?

- **Tight feedback loop.** Reviewer caught all 4 doc-sync violations in a single pass; builder responded with focused fixes across all 4 locations (directory listing, no_defaults count, board-native exception list, manifest converted list).
- **Skill delivery was solid on first try.** Builder created `planning/feature-decompose.md` (135 lines) and `composition.yaml` registration (no_defaults + comms-post + completion-report fragments) without structural issues — only docs were missing.
- **Test coverage was comprehensive.** All 4 acceptance criteria checked: file existence, composition.yaml structure, doc-sync presence in all 4 CLAUDE.md locations, and structural integrity.
- **No rework after fixes.** Once doc-sync violations were patched, review passed cleanly on the first retry.

---

## 2. What could have been better?

- **Builder didn't proactively sync docs.** The initial delivery included the skill file and composition.yaml but missed 4 doc-sync updates despite those being part of the skill registration workflow. Doc-sync should be bundled with any skill creation, not discovered by review.
- **Long turnaround on the second review pass.** Nearly 7 hours elapsed between the builder's fix and the second review for a 3-location doc patch — a simple checklist could have prevented the roundtrip.
- **Review had to flag, not prevent.** All 4 violations point to the same registration gap in CLAUDE.md, suggesting a single checklist or linter could have caught this upfront rather than after build.

---

## 3. What should we do differently next time?

- **Add doc-sync checklist to skill-creation prompts.** When builder registers a new skill, the prompt should explicitly list the 4 CLAUDE.md locations that require updates: directory listing, count fields, exception/list mentions, manifest conversions.
- **Integrate doc-sync checks into acceptance criteria.** Make it part of the skill's test suite so doc-sync violations fail the build before review even runs.
- **Consider a pre-commit lint step.** Add a simple schema validator for skill registrations that cross-checks CLAUDE.md against the actual skill directory and composition.yaml.

---

## Metrics

| Agent | Outcome | Tokens | Tools | Cost |
|---|---|---|---|---|
| builder (conv 1) | success | 18,000 | 14 | $0.0504 |
| reviewer (conv 1, attempt 1) | failed | 8,000 | 18 | $0.0432 |
| reviewer (conv 1, attempt 2) | success | 4,000 | 12 | $0.0216 |
| tester (conv 0) | success | 94,745 | 7 | $0.3075 |
| **Total** | **pass** | **124,745** | **51** | **$0.4227** |
