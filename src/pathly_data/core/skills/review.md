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

Before loading project rules, spawn a role-scoped scout to retrieve architectural rules applicable to the changed files:

Spawn `scout` with `ROLE: reviewer`:
```
ROLE: reviewer
What architectural rules, layer contracts, coding conventions, and dependency direction rules apply to these changed files: [list from git diff]?
Scope: ARCHITECTURE_PROPOSAL.md in the matching plans/ folder, project rule files, similar existing files in the same layer.
Return only rules directly relevant to the specific files that changed. 3–8 bullet points max.
```

Inject findings as `## Applicable Rules` before Step 2.
If no rule files exist and the scout finds nothing: proceed without injection.

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
