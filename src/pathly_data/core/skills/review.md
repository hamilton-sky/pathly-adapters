# review

This is the canonical, tool-agnostic Pathly behavior for the review workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

Review code at $ARGUMENTS against this project's architectural standards.

- `staged` or empty → review `git diff --staged`
- `last` → review `git diff HEAD~1 HEAD`
- file path → review that specific file

## Pre-review context gathering

**Phase 1 — Analyze:**
Spawn `reviewer` with `phase: analyze`. Pass the diff target (`$ARGUMENTS`).
Parse the returned `## NEEDS_CONTEXT` block.

**Phase 2 — Scout:**
If `NEEDS_CONTEXT` is not `none`: call `scout-path` with the block, `ROLE: reviewer`, `FEATURE: [changed area]`. Use the returned summary as findings.
If `NEEDS_CONTEXT` is `none`: findings = none.

**Phase 3 — Review:**
Spawn `reviewer` with the full review prompt. Inject:
```
## Applicable Rules
[compressed summary from Phase 2, or "none" if skipped]
```
Keep Steps 1–3 and the report format inside the reviewer's spawn prompt.

## Step 1 — Get the diff

Run the appropriate git diff command based on `$ARGUMENTS`.

## Step 2 — Load project rules

Read (if present):
1. The `ARCHITECTURE_PROPOSAL.md` in the `plans/*/` folder that most closely matches the changed files — defines the intended architecture for in-progress work
2. Project rule files — project-wide architectural contracts

If neither exists, review against general software engineering good practices and note the absence.

## Step 3 — Check for violations

For each changed file, check:

### Dependency direction
- Does the file import from a layer it should not depend on?
- Does the dependency direction match what `ARCHITECTURE_PROPOSAL.md` specifies?

### Layer responsibility
- Does the file contain logic that belongs in a different layer?
- Are concerns properly separated (e.g., data access vs. business logic vs. presentation)?

### Conventions
- Does the file follow naming and structural conventions shown in project rules?
- Are interfaces and contracts implemented correctly per the rules files?

### Scope
- Does the change touch files outside the scope described in the active conversation plan?
- Are there unexpected side effects on other modules?

## Report format

List each check as PASS / FAIL / N/A.

For failures use these prefixes:
```
[ARCH] <file>:<line> — <what the violation is> — <what it should be instead>
[IMPL] <file>:<line> — <what the violation is> — <fix required>
```

If all checks pass: `PASS — no violations found.`

If violations found: list each one. Do NOT auto-fix. Report only.
