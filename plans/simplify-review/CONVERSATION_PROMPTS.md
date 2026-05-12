# simplify-review — Conversation Guide

Split into 2 conversations. Each produces a clean, committable set of doc/schema changes.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Documentation fixes (Phases 1–3)

**Stories delivered:** S1.1, S1.2, S1.3, S1.4

**Prompt to paste:**
```
Read plans/simplify-review/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement simplify-review Conversation 1 (Phases 1–3) from plans/simplify-review/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read each file below to confirm it exists. Correct any discrepancy between the plan paths and reality before proceeding.

**Codebase files this conversation touches:**
- `docs/ARCHITECTURE.md` — remove hardcoded "20"; replace duplicate skill table with FLOW_DIAGRAM.md link
- `docs/PATHLY_ARCHITECTURE.md` — scope note; directory tree fix; team-flow annotation; consistent annotation style; fix pip install
- `README.md` — trim quick-start to ≤4 commands + link; /start equivalence note; fix Supported Hosts table; restore _meta/<name>.yaml; add Copilot skills destination
- `docs/FLOW_DIAGRAM.md` — complete trailing "…"; add verify→verify-state footnote; add Copilot branch to mermaid; add Copilot invocation examples block

Scope:
- Phase 1: ARCHITECTURE.md + PATHLY_ARCHITECTURE.md fixes (stories S1.1, S1.4) — see IMPLEMENTATION_PLAN.md Phase 1 Details
- Phase 2: README fixes (story S1.2) — see IMPLEMENTATION_PLAN.md Phase 2 Details
- Phase 3: FLOW_DIAGRAM.md fixes (story S1.3) — see IMPLEMENTATION_PLAN.md Phase 3 Details

Rules:
- Docs stories: criteria specify WHAT content must exist, not HOW it is formatted.
- Do NOT touch any Python files, _meta YAML files, or schema files.
- Do NOT touch any skill or agent .md files in src/.

Verify: run `git diff --stat` and confirm only the 4 listed doc files are modified.
After done, update plans/simplify-review/PROGRESS.md Phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Four doc files updated with no logic changes; `git diff --stat` shows exactly those four files.
**Files touched:** `docs/ARCHITECTURE.md`, `docs/PATHLY_ARCHITECTURE.md`, `README.md`, `docs/FLOW_DIAGRAM.md`

---

## Conversation 2: Schema fixes (Phase 4)

**Stories delivered:** S2.1

**Prompt to paste:**
```
Read plans/simplify-review/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement simplify-review Conversation 2 (Phase 4) from plans/simplify-review/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read each file below to confirm it exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `schemas/pathly-meta.schema.json` — add missing properties + constraints + descriptions
- `src/pathly_data/schemas/pathly-meta.schema.json` — sync with root; add required, enum, minLength, description fields

Scope — Phase 4:
1. Read both schema files in full.
2. Grep src/ and any _meta/ YAML files for `event:` keys to determine valid hook event names for the enum.
3. Add `natural_language` (string, minLength:1), `telemetry`, and `hooks` (array) to both schemas if absent.
4. In hooks.items: add `required: ["event", "script"]`.
5. In hooks[].event: add the `enum` of discovered event names.
6. In hooks[].script: add `description: "Shell command string to execute"`.
7. In `natural_language`: add `minLength: 1`.
8. In `host`: add `enum: ["claude", "codex", "copilot"]`.
9. Add a `description` to every property that lacks one in both files.
10. Apply identical changes to both files; diff them to confirm they are in sync.

Rules:
- Do NOT touch any doc files, Python files, or skill/agent .md files.
- Both schema files must be identical in structure after this conversation.

Verify: run `git diff --stat` and confirm only the 2 schema files are modified.
After done, update plans/simplify-review/PROGRESS.md Phase 4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Both schema files in sync, fully annotated, with constraints; `git diff --stat` shows exactly those two files.
**Files touched:** `schemas/pathly-meta.schema.json`, `src/pathly_data/schemas/pathly-meta.schema.json`
