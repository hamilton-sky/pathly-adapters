---
name: Implementation Plan
---
# adapter-parity — Implementation Plan

## Overview
Closes three gaps: (1) Copilot and Codex are missing `archive`, `archive-artifacts`, and `commit` skills; (2) the explorer agent has no core behavioral contract; (3) Copilot's `install.yaml` declares a `hooks:` block that the installer never executes. Also fixes hardcoded theme-breaking focus ring colors in the Studio.

## Layer Architecture

```
src/pathly_data/adapters/
  copilot/_meta/   ← add archive, archive-artifacts, commit skill YAMLs
  codex/_meta/     ← add commit skill YAML

src/pathly_data/core/agents/
  explorer.md      ← CREATE behavioral contract

src/pathly_data/adapters/copilot/_meta/
  install.yaml     ← remove dead hooks: block

studio/src/renderer/src/
  components/TopBar.module.css    ← token fix
  components/sidebar/Sidebar.module.css  ← token fix
```

## Prerequisite (pre-flight)
```
python -m pytest tests/ -q 2>&1 | head -40
```
Record any pre-existing failures as baseline.

## Phases

### Phase 1: Copilot archive + archive-artifacts skills   ← Conversation: 1
**File:** `src/pathly_data/adapters/copilot/_meta/archive_skill.yaml`, `src/pathly_data/adapters/copilot/_meta/archive-artifacts_skill.yaml`
**Done when:** Both files exist, are valid YAML, and pass `python tools/check_core.py` (or equivalent lint).
**Delivers stories:** S1
**Depends on:** nothing
**Enables:** Phase 2
**Details:**
- Read `src/pathly_data/adapters/claude/_meta/archive_skill.yaml` for the exact schema
- Copy content verbatim; the only field that may differ is `host:` if it exists — set to `copilot`
- Same for `archive-artifacts_skill.yaml`
- Do NOT change the `skill:`, `filename:`, or `natural_language:` values

### Phase 2: Copilot + Codex commit skill   ← Conversation: 1
**File:** `src/pathly_data/adapters/copilot/_meta/commit_skill.yaml`, `src/pathly_data/adapters/codex/_meta/commit_skill.yaml`
**Done when:** Both files exist and are valid YAML.
**Delivers stories:** S2
**Depends on:** Phase 1 (same conversation, independent content)
**Details:**
- Read `src/pathly_data/adapters/claude/_meta/commit_skill.yaml`
- Copy with host field adjusted as needed

### Phase 3: explorer.md behavioral contract   ← Conversation: 1
**File:** `src/pathly_data/core/agents/explorer.md`
**Done when:** File exists with frontmatter + role description consistent with `explorer.yaml` in all three adapters.
**Delivers stories:** S3
**Depends on:** nothing
**Details:**
- Read the `description:` field from `src/pathly_data/adapters/claude/_meta/explorer.yaml`
- Read `src/pathly_data/core/agents/scout.md` as a structural template (explorer and scout are similar read-only agents)
- Write `explorer.md` with:
  - Frontmatter: `name: explorer`, `description: <from yaml>`, `model:`, `tools: [Read, Glob, Grep, Write]`
  - Role: read-only codebase path tracer; answers "how does X work", "is it safe to change Y"
  - Outputs: NEEDS_CONTEXT (analyze phase), TRACE.md (explore phase), CONCLUSIONS.md (conclude phase)
  - Never edits source code or runs commands

### Phase 4: Remove dead hooks: block from Copilot install.yaml   ← Conversation: 2
**File:** `src/pathly_data/adapters/copilot/_meta/install.yaml`
**Done when:** `hooks:` key is absent from the file; `pathly-setup --dry-run` for copilot produces no hook-related output.
**Delivers stories:** S4
**Depends on:** nothing
**Details:**
- Read the current `install.yaml` to locate the `hooks:` block
- Remove the entire `hooks:` key and its list entries
- Do NOT touch any other key in the file
- Decision rationale: implementing hooks requires wiring in `setup_command.py` and proper Copilot extension directory detection — scope that as a future feature, not this fix

### Phase 5: Replace hardcoded focus ring colors in Studio   ← Conversation: 3
**File:** `studio/src/renderer/src/components/TopBar.module.css`, `studio/src/renderer/src/components/sidebar/Sidebar.module.css`
**Done when:** Zero occurrences of the literal string `#89b4fa` in either file; `filterInput` has a `:focus-visible` rule.
**Delivers stories:** S5
**Depends on:** nothing
**Details:**
- In both files, replace every `outline: 2px solid #89b4fa` with `outline: var(--focus-ring)`
- Also replace `outline: 2px solid var(--accent, #89b4fa)` with `outline: var(--focus-ring)` (the fallback is wrong — the theme token IS the right value)
- In `Sidebar.module.css` `.filterInput`: the current rule has `outline: none` — add a separate `:focus-visible` rule:
  ```css
  .filterInput:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  ```
- Also replace hardcoded `#8B5CF6` in `.dropTarget` with `var(--accent)` (or add a `--drag-accent` token if a different color is desired)
**Verify:** `npm run build` in studio/ succeeds; visually verify focus ring color changes with different themes in the Settings panel

## Key Decisions
- Hooks removal (Option A): removing is lower risk than a partial implementation; hooks can be added as a full feature with proper testing
- explorer.md modeled on scout.md: explorer is the "trace a code path" variant of scout's "answer a structural question" role — same tool set, different output contract
