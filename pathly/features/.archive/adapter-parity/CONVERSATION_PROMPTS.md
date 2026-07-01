---
name: Conversation Guide
---
# adapter-parity — Conversation Guide

Split into 3 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Copilot/Codex skill parity + explorer contract (Phases 1-3)

**Stories delivered:** S1, S2, S3

**Prompt to paste:**
```
Read pathly/plans/adapter-parity/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement adapter-parity Conversation 1 (Phases 1-3) from pathly/plans/adapter-parity/IMPLEMENTATION_PLAN.md.

**Before creating anything:** read these source files to understand the exact schema:
- `src/pathly_data/adapters/claude/_meta/archive_skill.yaml`
- `src/pathly_data/adapters/claude/_meta/archive-artifacts_skill.yaml`
- `src/pathly_data/adapters/claude/_meta/commit_skill.yaml`
- `src/pathly_data/adapters/claude/_meta/explorer.yaml`
- `src/pathly_data/core/agents/scout.md` (structural template for explorer.md)

**Phase 1 — Copilot archive skills:**
- Create `src/pathly_data/adapters/copilot/_meta/archive_skill.yaml` — exact copy of the Claude version; adjust `host:` field to `copilot` if that field exists, otherwise copy verbatim
- Create `src/pathly_data/adapters/copilot/_meta/archive-artifacts_skill.yaml` — same approach

**Phase 2 — Copilot + Codex commit skill:**
- Create `src/pathly_data/adapters/copilot/_meta/commit_skill.yaml` — copy from Claude
- Create `src/pathly_data/adapters/codex/_meta/commit_skill.yaml` — copy from Claude, adjust host if needed

**Phase 3 — explorer.md behavioral contract:**
- Create `src/pathly_data/core/agents/explorer.md`
- Use scout.md as the structural template (same frontmatter shape)
- Role: read-only codebase path tracer — traces code paths and answers structural questions (how does X work, is it safe to change Y)
- Tool set: Read, Glob, Grep, Write (Write only for output files like TRACE.md and CONCLUSIONS.md)
- Three phases: analyze (outputs NEEDS_CONTEXT), explore (writes TRACE.md), conclude (writes CONCLUSIONS.md)
- Constraint: Read-only on production code. Never edits source or runs Bash.
- The description must match the `description:` field in `src/pathly_data/adapters/claude/_meta/explorer.yaml`

Architectural rules:
- Do not modify any existing YAML files — only create new ones.
- Do not touch studio/, install_cli/, or telemetry files.
- Copy schema exactly — do not invent new YAML fields.

Do NOT touch install.yaml or TopBar.module.css yet.
Verify: `python tools/check_core.py` passes (if the tool checks new files); all 5 new files are valid YAML.
After done, update pathly/plans/adapter-parity/PROGRESS.md phases 1-3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 5 new files created; all valid YAML; explorer.md behavioral contract written.
**Files touched:** 5 new files (4 YAML + 1 Markdown)

---

## Conversation 2: Remove dead Copilot hooks config (Phase 4)

**Stories delivered:** S4

**Prompt to paste:**
```
Read pathly/plans/adapter-parity/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement adapter-parity Conversation 2 (Phase 4) from pathly/plans/adapter-parity/IMPLEMENTATION_PLAN.md.

**Before editing:** read `src/pathly_data/adapters/copilot/_meta/install.yaml` in full. Note the exact location and content of the `hooks:` key.

**Phase 4 — Remove dead hooks: block:**
- In `src/pathly_data/adapters/copilot/_meta/install.yaml`: delete the entire `hooks:` key and all its list entries
- Leave all other keys (`host:`, `destination:`, `files:`, `telemetry:`, etc.) exactly as they are
- The resulting file must be valid YAML — verify by reading it back mentally

Decision context: The `hooks:` block declares files that the installer (`setup_command.py`) never materializes. Implementing hooks properly is a future feature. Removing it now prevents a confusing gap between declared config and actual behavior.

Architectural rules:
- Only touch `install.yaml`. Do not touch setup_command.py, other adapter install.yaml files, or studio files.

Do NOT touch archive_skill.yaml, TopBar.module.css, or Python files.
Verify: `python -m pytest tests/ -q` passes (tests should not reference hooks for copilot).
After done, update pathly/plans/adapter-parity/PROGRESS.md phase 4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `hooks:` key removed from Copilot install.yaml; file is valid YAML.
**Files touched:** `src/pathly_data/adapters/copilot/_meta/install.yaml`

---

## Conversation 3: Studio focus ring token fixes (Phase 5)

**Stories delivered:** S5

**Prompt to paste:**
```
Read pathly/plans/adapter-parity/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement adapter-parity Conversation 3 (Phase 5) from pathly/plans/adapter-parity/IMPLEMENTATION_PLAN.md.

**Before editing:** read both files in full:
- `studio/src/renderer/src/components/TopBar.module.css`
- `studio/src/renderer/src/components/sidebar/Sidebar.module.css`

Note every occurrence of `#89b4fa` and any `outline: none` on `.filterInput`.

**Phase 5 — Focus ring token replacement:**
In TopBar.module.css:
- Replace every `outline: 2px solid #89b4fa` with `outline: var(--focus-ring)`
- Replace every `outline: 2px solid var(--accent, #89b4fa)` with `outline: var(--focus-ring)`
- The `--focus-ring` token is defined in `tokens.css` as `2px solid <accent-color>` per theme — it is the correct replacement

In Sidebar.module.css:
- Same replacements for all `#89b4fa` occurrences
- For `.filterInput`: it currently has `outline: none` on focus. Add a new rule:
  ```css
  .filterInput:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  ```
  Keep the existing `.filterInput:focus { border-color: var(--accent); }` rule — they complement each other.
- Replace the hardcoded `#8B5CF6` in `.dropTarget` rule with `var(--accent)` for the border and use `rgba(var(--accent-rgb, 56 189 248) / 0.08)` for background — or simply use `var(--accent-bg)` for the background if that token gives sufficient visual contrast.

Architectural rules:
- Only touch TopBar.module.css and Sidebar.module.css. Do not touch tokens.css or any TypeScript files.
- Do not change any layout, padding, or non-color properties.

Do NOT touch Python files, YAML files, or FlowEditor files.
Verify: `npm run build` in studio/ succeeds without errors.
After done, update pathly/plans/adapter-parity/PROGRESS.md phase 5 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Zero `#89b4fa` literals in both CSS files; filterInput keyboard-accessible.
**Files touched:** `TopBar.module.css`, `Sidebar.module.css`
