---
name: User Stories
---
# antigravity-adapter — User Stories

## Context
`pathly-adapters` currently ships three AI host adapters: `claude`, `codex`, and `copilot`. Each adapter is a directory under `src/pathly_data/adapters/` containing `_meta/` YAML files (one per agent, one per skill) and an `install.yaml` config. `pathly-setup <host> --apply` stitches core agent and skill markdown with host-specific metadata and deploys the result to the host's config directory.

Google Antigravity (`agy` CLI) was launched in November 2025 (v2.0 at Google I/O May 2026) and has a skill/agent architecture directly analogous to Claude Code's — skills stored in a nested `<skill>/SKILL.md` structure, lifecycle hooks, MCP support, and sub-agent spawning. This feature adds a fourth `antigravity` adapter so `pathly-setup antigravity --apply` works end-to-end.

---

## Stories

### Story S1.1: Adapter infrastructure
**As a** developer installing Pathly, **I want** `pathly-setup antigravity --apply` to run without errors, **so that** the adapter directory, detection, and install config are all wired up before any agent or skill files are created.

**Acceptance Criteria:**
- [ ] `"antigravity"` appears in `ALLOWED_HOSTS` in `src/install_cli/orchestrate.py`
- [ ] `"antigravity"` key exists in `_HOST_MARKERS` in `src/install_cli/detect.py` with at least one detection path (e.g. `~/.gemini/antigravity-cli` or `~/.gemini`)
- [ ] `src/pathly_data/adapters/antigravity/_meta/install.yaml` exists with valid `host`, `destination`, `skills.destination`, `skills.structure`, and `templates.destination` fields
- [ ] `src/pathly_data/adapters/antigravity/README.md` exists with install instructions

**Edge Cases:**
- `~/.gemini/` does not exist on the machine — detection returns false, `pathly-setup` (no args) silently skips antigravity
- `pathly-setup antigravity --dry-run` runs without error even if `~/.gemini/` does not exist

**Delivered by:** Phase 0–2 → Conversation 1

---

### Story S1.2: Host auto-detection
**As a** user with Antigravity installed, **I want** `pathly-setup` (no args) to detect my Antigravity installation automatically, **so that** I don't have to specify `antigravity` explicitly.

**Acceptance Criteria:**
- [ ] When `~/.gemini/antigravity-cli/` exists, `detect_hosts()` includes `"antigravity"` in its return value
- [ ] When `~/.gemini/antigravity-cli/` does not exist, `detect_hosts()` does not include `"antigravity"`

**Edge Cases:**
- Only `~/.gemini/` exists (not `antigravity-cli/` subdirectory) — whether to detect depends on the chosen detection path; builder must choose the most specific path that won't false-positive on unrelated Gemini tooling

**Delivered by:** Phase 2 → Conversation 1

---

### Story S2.1: Agent YAML files
**As an** Antigravity user, **I want** all Pathly agent role contracts deployed to Antigravity's agent directory with correct Gemini model assignments, **so that** agents can be invoked by the `agy` CLI with the right models and capabilities.

**Acceptance Criteria:**
- [ ] `src/pathly_data/adapters/antigravity/_meta/` contains exactly 11 agent YAML files: `architect.yaml`, `builder.yaml`, `director.yaml`, `explorer.yaml`, `planner.yaml`, `po.yaml`, `quick.yaml`, `reviewer.yaml`, `scout.yaml`, `tester.yaml`, `web-researcher.yaml`
- [ ] Each YAML file has `name`, `description`, and `model` fields
- [ ] High-capability agents (architect) use a `pro`-tier Gemini model; standard agents (builder, reviewer, planner, etc.) use a `flash`-tier model; fast agents (quick, scout, orchestrator) use a `flash` or lighter model
- [ ] Model names are taken from `agy models list` output (verified during Phase 0 pre-flight), not guessed
- [ ] A `pathly-setup antigravity --dry-run` after Conv 2 shows 11 agent files listed under the agents destination

**Edge Cases:**
- Antigravity may not support a `tools` field in agent YAML — omit if unsupported, matching whichever fields the `agy` CLI agent format accepts
- A model name verified during pre-flight may be deprecated in a future Antigravity release — document the chosen names in `README.md`

**Delivered by:** Phase 3 → Conversation 2

---

### Story S3.1: Skill YAML files
**As an** Antigravity user, **I want** all 19 Pathly skills available via the `agy` CLI, **so that** I can run commands like `agy "pathly go"` or invoke `/pathly build` from the Antigravity skill menu.

**Acceptance Criteria:**
- [ ] `src/pathly_data/adapters/antigravity/_meta/` contains exactly 19 skill YAML files matching the claude adapter's set: `archive`, `build`, `end`, `go`, `help`, `lessons`, `meet`, `pause`, `pathly`, `plan`, `po`, `prd-import`, `retro`, `review`, `scout-path`, `start`, `storm`, `test`, `verify-state`
- [ ] Each skill YAML has `skill` and `natural_language` fields; `filename` field follows the nested pattern `<skill>/SKILL.md` (matching codex structure)
- [ ] `pathly-setup antigravity --dry-run` after Conv 3 lists 19 skill files under the skills destination
- [ ] `python -m pytest tests/ -q` passes with no new failures after Conv 3

**Edge Cases:**
- Skill YAMLs that match the claude adapter exactly (same `natural_language`) are correct — no Antigravity-specific wording needed
- If Antigravity uses a different skill file format, the `stitch_skill` function in `stitch.py` handles the frontmatter generation automatically

**Delivered by:** Phase 4 → Conversation 3

---

### Story S4.1: Test coverage
**As a** developer, **I want** the existing test suite to include antigravity-specific assertions, **so that** regressions in detection and install are caught automatically.

**Acceptance Criteria:**
- [ ] `tests/test_setup.py` includes assertions that `"antigravity"` is in `_HOST_MARKERS` and that detection returns `True` when the marker directory exists
- [ ] `tests/test_e2e_install.py` includes a `@pytest.mark.slow` test that runs `pathly-setup antigravity --dry-run` and asserts exit 0 and `"[antigravity]"` in stdout
- [ ] `python -m pytest tests/ -q` passes with all new tests

**Edge Cases:**
- The e2e test must create the antigravity detection directory in `tmp_path` (same pattern as the existing claude test) so it doesn't depend on the real filesystem

**Delivered by:** Phase 5 → Conversation 4
