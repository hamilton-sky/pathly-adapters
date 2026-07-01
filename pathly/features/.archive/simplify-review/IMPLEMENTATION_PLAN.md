# simplify-review — Implementation Plan

## Overview
Apply all 23 documentation and schema quality findings from the /simplify review. Conversation 1 fixes four doc files; Conversation 2 syncs and enriches two schema files. No Python code changes.

## Pre-flight
Before starting Conversation 1, run `git status` to confirm a clean working tree. No test suite to baseline — this feature has no runnable tests.

## Phases

### Phase 1: ARCHITECTURE.md + PATHLY_ARCHITECTURE.md fixes   ← Conversation: 1
**File:** `docs/ARCHITECTURE.md` — MODIFY: remove hardcoded "20" from skills directory comment; replace duplicate skill table with a cross-reference link to FLOW_DIAGRAM.md
**File:** `docs/PATHLY_ARCHITECTURE.md` — MODIFY: add scope header note; fix directory tree (one file per line); add team-flow entry-point comment; unify annotation style; fix pip install command to `pip install -e ".[dev]"`
**Done when:** Neither ARCHITECTURE.md nor PATHLY_ARCHITECTURE.md contain a standalone skill command table; PATHLY_ARCHITECTURE.md has a header note distinguishing its scope.
**Delivers stories:** S1.1, S1.4
**Depends on:** nothing
**Enables:** Phase 2 (README links to FLOW_DIAGRAM.md as the canonical source, so the table must be removed first)

**Details:**
- ARCHITECTURE.md: find and replace the skill command table with a single line such as: `See [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md) for the full command reference.`
- ARCHITECTURE.md: remove the hardcoded "20" from any comment referencing the skills directory.
- PATHLY_ARCHITECTURE.md: add a `> **Scope:**` or `## Scope` note at the top of the doc explaining it covers install/package layout, while ARCHITECTURE.md covers runtime adapter surfaces.
- PATHLY_ARCHITECTURE.md: in the directory tree, expand any comma-separated file lists (e.g. `start.md, go.md, build.md`) — put each on its own line or replace with `…` and a note it is abbreviated.
- PATHLY_ARCHITECTURE.md: beside `team-flow.md` add a comment `← entry point`; beside `team-flow/` add `← sub-skills`.
- PATHLY_ARCHITECTURE.md: either annotate every notable file or remove the lone `← dispatcher` on pathly.md (choose one style consistently).
- PATHLY_ARCHITECTURE.md: replace any `pip install -e pathly-adapters/` with `pip install -e ".[dev]"`.

---

### Phase 2: README fixes   ← Conversation: 1
**File:** `README.md` — MODIFY: trim quick-start; add invocation equivalence note; fix Supported Hosts table; restore meta path; add Copilot skills destination
**Done when:** README quick-start block has ≤4 commands with a link to FLOW_DIAGRAM.md; README explains /start and /pathly start equivalence; Supported Hosts table has separate rows/lines for agents and skills directories; How It Works shows `_meta/<name>.yaml`; Copilot row includes a skills destination.
**Delivers stories:** S1.2
**Depends on:** Phase 1 complete (FLOW_DIAGRAM.md is the link target)
**Enables:** Phase 3

**Details:**
- Quick-start block: keep at most 4 representative commands; add a line `See [FLOW_DIAGRAM.md](docs/FLOW_DIAGRAM.md) for the full command reference.`
- Add a note (e.g. in a tip block or parenthetical): `/start` and `/pathly start` are equivalent; `/pathly` dispatches to the same skill, while direct invocation skips the dispatcher.
- Supported Hosts table: in the Claude Code row, if the cell lists `~/.claude/agents/ + ~/.claude/skills/`, split into two sub-lines or two columns so each path is clearly labeled.
- How It Works: restore `_meta/<name>.yaml` (revert any change to a glob pattern).
- Supported Hosts table: in the Copilot row, add the skills destination alongside the existing VS Code agents folder entry.

---

### Phase 3: FLOW_DIAGRAM.md fixes   ← Conversation: 1
**File:** `docs/FLOW_DIAGRAM.md` — MODIFY: complete prose; add verify footnote; add Copilot branch to mermaid; add Copilot invocation block
**Done when:** Line 10 prose is a complete sentence; invocation table has a footnote for the verify→verify-state mapping; mermaid diagram has a Copilot branch; a Copilot invocation examples block exists.
**Delivers stories:** S1.3
**Depends on:** Phase 2 complete
**Enables:** Conv 2

**Details:**
- Line 10: find the trailing "…" and complete the sentence with appropriate content about host entry points.
- Invocation table footnote: add `* /pathly verify dispatches to verify-state (different stem from all other /pathly <x> → <x> pairs).`
- Mermaid diagram: add a `Copilot` node/branch alongside the existing Claude Code and Codex branches with an equivalent invocation path.
- Copilot invocation examples block: add a section parallel in structure to the existing Claude Code table and Codex block, showing equivalent Copilot commands.

---

### Phase 4: Schema sync and enrichment   ← Conversation: 2
**File:** `schemas/pathly-meta.schema.json` — MODIFY: add missing properties, constraints, descriptions
**File:** `src/pathly_data/schemas/pathly-meta.schema.json` — MODIFY: add `required`, `enum`, `minLength`, `description` fields
**Done when:** Both schema files contain `natural_language`, `telemetry`, and `hooks` properties; `hooks.items` has `required: ["event", "script"]`; `hooks[].event` has an `enum`; every property has a `description`; `natural_language` has `minLength: 1`; `host` has `enum: ["claude", "codex", "copilot"]`.
**Delivers stories:** S2.1
**Depends on:** Conv 1 complete (independent, but keep sequenced for clean commits)
**Enables:** nothing (final phase)

**Details:**
- Read both schema files in full before editing either.
- Determine the canonical set of hook event names by grepping the source for hook usage (look in `src/` and `_meta/` YAML files for `event:` keys).
- Add `natural_language` (type: string, minLength: 1, description), `telemetry` (type: object or boolean, description), and `hooks` (type: array, description) to the root schema `properties` if absent.
- In `hooks.items`: add `required: ["event", "script"]`.
- In `hooks[].event`: add `enum` of the known event names discovered above.
- In `hooks[].script`: add `description: "Shell command string to execute"` and optionally `format: "shell-command"`.
- In `host`: add `enum: ["claude", "codex", "copilot"]`.
- Add a `description` annotation to every property that lacks one in both files.
- Apply identical changes to both files. Verify they are in sync by diffing them after editing.

---

## Prerequisites
- Clean working tree before Conversation 1

## Key Decisions
- Docs stories: criteria specify WHAT content must exist, not HOW it is formatted (per LESSONS CANDIDATE-001)
- Each criterion is independently falsifiable — implied criteria removed (per LESSONS CANDIDATE-002)
- Hook event enum values must be derived from actual source usage, not guessed
