# simplify-review — User Stories

## Context
The /simplify review identified 23 documentation and schema quality findings across four doc files and two schema files. This feature applies all findings: no code logic changes — docs and schema only.

## Stories

### Story 1.1: Cross-reference deduplication in ARCHITECTURE.md and PATHLY_ARCHITECTURE.md
**As a** contributor, **I want** the skill command table to live in one place, **so that** readers are directed to the canonical source instead of encountering stale copies.

**Acceptance Criteria:**
- [ ] ARCHITECTURE.md does not contain a duplicate skill command table; it links to FLOW_DIAGRAM.md instead
- [ ] PATHLY_ARCHITECTURE.md does not contain a duplicate skill command table; it links to FLOW_DIAGRAM.md instead

**Delivered by:** Phase 1 → Conversation 1

---

### Story 1.2: README clarity and correctness
**As a** new user, **I want** the README to accurately reflect invocation options and host details, **so that** I can set up pathly without confusion.

**Acceptance Criteria:**
- [ ] README quick-start block shows ≤4 illustrative commands with a "See full table →" link to FLOW_DIAGRAM.md
- [ ] README explains that /start and /pathly start are equivalent alternatives
- [ ] README Supported Hosts table has separate lines for `~/.claude/agents/` and `~/.claude/skills/`
- [ ] README How It Works section references `_meta/<name>.yaml` (not the glob form)
- [ ] README Supported Hosts table includes a skills destination for the Copilot row

**Delivered by:** Phase 2 → Conversation 1

---

### Story 1.3: FLOW_DIAGRAM.md completeness and Copilot coverage
**As a** contributor, **I want** FLOW_DIAGRAM.md to be complete and include Copilot, **so that** it is the authoritative reference it claims to be.

**Acceptance Criteria:**
- [ ] FLOW_DIAGRAM.md line 10 prose has no trailing "…"; the sentence is complete
- [ ] FLOW_DIAGRAM.md has a footnote explaining the /pathly verify → verify-state stem mismatch
- [ ] FLOW_DIAGRAM.md mermaid diagram includes Copilot as a branch alongside Claude Code and Codex
- [ ] FLOW_DIAGRAM.md has a Copilot invocation examples block parallel to the Claude Code table

**Delivered by:** Phase 3 → Conversation 1

---

### Story 1.4: PATHLY_ARCHITECTURE.md structural fixes
**As a** contributor, **I want** PATHLY_ARCHITECTURE.md to accurately describe the package structure and install command, **so that** its scope is unambiguous.

**Acceptance Criteria:**
- [ ] PATHLY_ARCHITECTURE.md has a header note distinguishing its scope (install/package) from ARCHITECTURE.md (runtime adapter surfaces)
- [ ] PATHLY_ARCHITECTURE.md directory tree has each file on its own line (no comma-separated filenames)
- [ ] PATHLY_ARCHITECTURE.md has a comment identifying `team-flow.md` as the entry point and `team-flow/` as sub-skills
- [ ] PATHLY_ARCHITECTURE.md uses one consistent annotation style (all files annotated, or only notable ones)
- [ ] PATHLY_ARCHITECTURE.md install command uses `pip install -e ".[dev]"`

**Delivered by:** Phase 1 → Conversation 1

---

### Story 2.1: Schema sync and enrichment
**As a** tooling author, **I want** both schema files to be in sync and fully annotated, **so that** editors and validators produce accurate hints.

**Acceptance Criteria:**
- [ ] `schemas/pathly-meta.schema.json` contains `natural_language`, `telemetry`, and `hooks` properties
- [ ] `src/pathly_data/schemas/pathly-meta.schema.json` contains `natural_language`, `telemetry`, and `hooks` properties
- [ ] `hooks.items` has `required: ["event", "script"]` in both files
- [ ] `hooks[].event` has an `enum` of valid event names in both files
- [ ] `hooks[].script` has a `description` field in both files
- [ ] `natural_language` has `minLength: 1` in both files
- [ ] `host` has `enum: ["claude", "codex", "copilot"]` in both files
- [ ] Every property has a `description` annotation in both files

**Delivered by:** Phase 4 → Conversation 2
