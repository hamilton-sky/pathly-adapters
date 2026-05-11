# Plan: simplify-review
Rigor: lite | Source: docs/SIMPLIFY_REVIEW.md (commit 4165cf3)

## Goal
Implement the 23 documentation and schema quality findings from the /simplify review.
No code logic changes — docs and schema only.

## Conversations

### Conv 1 — Documentation fixes (README.md, FLOW_DIAGRAM.md, ARCHITECTURE.md, PATHLY_ARCHITECTURE.md)

**1.1** ARCHITECTURE.md and PATHLY_ARCHITECTURE.md re-list the skill command table;
replace with a cross-reference link to FLOW_DIAGRAM.md (canonical source).

**1.2** README.md quick-start block duplicates the full command table in FLOW_DIAGRAM.md;
trim to ≤4 illustrative commands and add a "See full table →" link.

**1.3** PATHLY_ARCHITECTURE.md and ARCHITECTURE.md scope overlap (both list 20 skills);
add a header note to PATHLY_ARCHITECTURE.md that states its scope (install/package),
distinguishing it from ARCHITECTURE.md (runtime adapter surfaces).

**2.2** README.md: explain that /start and /pathly start are equivalent alternatives;
/pathly dispatches to the same skill, direct invocation skips the dispatcher.

**2.3** README.md Supported Hosts table: split `~/.claude/agents/ + ~/.claude/skills/`
into two lines within the cell (or a note) so it renders clearly.

**2.4** README.md How It Works: restore `_meta/<name>.yaml` (was changed to glob `_meta/*.yaml`).

**2.5** FLOW_DIAGRAM.md line 10: complete trailing "…" in Host Entry Points prose.

**2.6** ARCHITECTURE.md: remove hardcoded count "20" from the skills directory comment.

**2.7** PATHLY_ARCHITECTURE.md: fix comma-separated filenames in directory tree
(e.g. `start.md, go.md, build.md, plan.md`) — each file on its own line or note
that it is an abbreviated listing.

**2.8** PATHLY_ARCHITECTURE.md: add a comment explaining that `team-flow.md` is the
entry point and `team-flow/` holds sub-skills.

**2.9** PATHLY_ARCHITECTURE.md: either annotate all notable files or remove the lone
`← dispatcher` annotation on pathly.md; choose one style.

**2.10** PATHLY_ARCHITECTURE.md: fix `pip install -e pathly-adapters/` → use
`pip install -e ".[dev]"` (matching README dev setup).

**3.1** FLOW_DIAGRAM.md invocation table: add a footnote explaining why `/pathly verify`
maps to `/verify-state` (different stem from all other pairs).

**3.2** README.md Supported Hosts: add skills destination for Copilot row
(currently only shows "VS Code agents folder").

**3.3** FLOW_DIAGRAM.md mermaid diagram: add Copilot as a third branch alongside
Claude Code and Codex.

**3.4** FLOW_DIAGRAM.md: add a Copilot invocation examples block, parallel to the
existing Claude Code table and Codex block.

### Conv 2 — Schema fixes (both pathly-meta.schema.json files)

**3.5** Sync `schemas/pathly-meta.schema.json` (root) with the `src/` copy:
add the missing `natural_language`, `telemetry`, and `hooks` properties.

**4.1** `hooks.items`: add `required: ["event", "script"]`.

**4.2** `hooks[].event`: add `enum` of known hook event names.
(Need to read hook usage in source to determine valid values.)

**4.3** `hooks[].script`: add `description` and `format` note (shell command string).

**4.4** `natural_language`: add `minLength: 1`.

**4.5** `host`: add `enum: ["claude", "codex", "copilot"]`.

**4.6** All properties: add `description` annotation.

Apply all schema fixes to both files (root and src/).

## Out of scope
- No Python code changes
- No changes to _meta YAML adapter files
- No changes to core agent/skill .md files
