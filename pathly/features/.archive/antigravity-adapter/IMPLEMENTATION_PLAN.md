---
name: Implementation Plan
---
# antigravity-adapter — Implementation Plan

## Overview
Adds `antigravity` as a fourth Pathly host adapter alongside `claude`, `codex`, and `copilot`. The work spans four files in `src/install_cli/` (detection + ALLOWED_HOSTS), one new `_meta/install.yaml`, eleven agent YAML files, nineteen skill YAML files, and two test files. No core skill or agent markdown changes are needed — the adapter is purely configuration.

## Layer Architecture

```
src/pathly_data/adapters/antigravity/_meta/  ← per-agent + per-skill YAML (host metadata)
          ↓  pathly-setup antigravity --apply
src/install_cli/orchestrate.py               ← stitches core/ + _meta/ → deployable files
          ↓
~/.gemini/antigravity-cli/agents/            ← deployed agent .md files
~/.gemini/antigravity-cli/skills/            ← deployed skill/<SKILL.md> files
~/.gemini/antigravity-cli/plugins/pathly/    ← plan templates
```

---

## Prerequisites

- `agy` CLI is accessible in PATH: run `agy --version` to confirm
- Run `agy models list` (or check Antigravity docs) and record the exact model names for pro-tier and flash-tier before writing any agent YAML files
- Existing tests pass: `python -m pytest tests/ -q` exits 0

---

## Phases

### Phase 0: Pre-flight verification   ← Conversation: 1
**File:** *(no file written — verification only)*
**Done when:** `agy --version` runs without error OR the limitation is documented; model names are recorded; `python -m pytest tests/ -q` exits 0 and the baseline is noted.
**Delivers stories:** prerequisite for all stories
**Depends on:** nothing
**Enables:** Phase 1 — model names must be known before writing agent YAMLs
**Details:**
- Run `agy --version` (or `where agy`) to confirm the binary is present. If absent, document the limitation in `README.md` and use placeholder model names `gemini-2.5-pro` and `gemini-2.5-flash` with a TODO note.
- Run `agy models list` or consult `https://antigravity.google/docs/cli-getting-started` to get current model names. Record the pro-tier model (for architect) and flash-tier model (for builder/reviewer/planner) and a lite/flash model (for quick/scout).
- Run `python -m pytest tests/ -q` and record any pre-existing failures as baseline. Do not fix pre-existing failures in this feature.
**Verify:** `python -m pytest tests/ -q` (record baseline — do not require 0 failures if pre-existing)

---

### Phase 1: Adapter directory and install config   ← Conversation: 1
**File:** `src/pathly_data/adapters/antigravity/_meta/install.yaml` — CREATE
**Done when:** the file exists, is valid YAML, and contains `host: antigravity`, `destination`, `skills.destination`, `skills.structure: nested`, and `templates.destination`.
**Delivers stories:** S1.1
**Depends on:** Phase 0 (model names don't affect this phase; path conventions from Antigravity docs do)
**Enables:** Phase 2 and all subsequent phases (orchestrate.py reads install.yaml at install time)
**Details:**
- Create `src/pathly_data/adapters/antigravity/_meta/install.yaml`:
  ```yaml
  host: antigravity
  destination: ~/.gemini/antigravity-cli/agents/
  skills:
    destination: ~/.gemini/antigravity-cli/skills/
    structure: nested
  templates:
    destination: ~/.gemini/antigravity-cli/plugins/pathly/templates
  telemetry: true
  ```
- Create `src/pathly_data/adapters/antigravity/README.md` with: install instructions (`pathly-setup antigravity --apply`), the `agy` binary install command, skills directory location, and any model name TODO items discovered in Phase 0.
- **Note on install paths:** `~/.gemini/antigravity-cli/agents/` mirrors the Antigravity CLI's global agent discovery path (analogous to `~/.claude/agents/` and `~/.codex/agents/`). Verify this path against `agy` docs or `agy --help` before finalizing. If the correct path differs, update `install.yaml` accordingly.
**Verify:** `python -c "import yaml; d=yaml.safe_load(open('src/pathly_data/adapters/antigravity/_meta/install.yaml')); assert d['host']=='antigravity'"`

---

### Phase 2: Wire up detection and ALLOWED_HOSTS   ← Conversation: 1
**File:** `src/install_cli/detect.py` and `src/install_cli/orchestrate.py` — MODIFY
**Done when:** `"antigravity"` is in `ALLOWED_HOSTS` in `orchestrate.py`; `"antigravity"` is a key in `_HOST_MARKERS` in `detect.py` with at least one `Path` entry; `python -m pytest tests/ -q` exits with no new failures.
**Delivers stories:** S1.1, S1.2
**Depends on:** Phase 1 (install.yaml must exist for orchestrate.py to find it)
**Enables:** Phase 3 (agent YAMLs won't be processed without ALLOWED_HOSTS entry)
**Details:**
- In `src/install_cli/orchestrate.py`, add `"antigravity"` to the `ALLOWED_HOSTS` set (line ~26):
  ```python
  ALLOWED_HOSTS = {"antigravity", "claude", "codex", "copilot"}
  ```
- In `src/install_cli/detect.py`, add detection markers:
  ```python
  "antigravity": [
      Path.home() / ".gemini" / "antigravity-cli",
  ],
  ```
  Use `~/.gemini/antigravity-cli` (not just `~/.gemini`) to avoid false-positive detection on machines that have Gemini CLI but not Antigravity. If Antigravity installs a different marker directory, use that instead.
**Verify:** `python -c "from install_cli.orchestrate import ALLOWED_HOSTS; assert 'antigravity' in ALLOWED_HOSTS, 'missing from ALLOWED_HOSTS'"` and `python -m pytest tests/ -q`

---

### Phase 3: Agent YAML files   ← Conversation: 2
**File:** `src/pathly_data/adapters/antigravity/_meta/<agent>.yaml` × 11 — CREATE
**Done when:** exactly 11 agent YAML files exist in `src/pathly_data/adapters/antigravity/_meta/` (none ending in `_skill.yaml`), each valid YAML with `name`, `description`, and `model` fields; `python -m install_cli antigravity --dry-run` lists 11 agents in its output.
**Delivers stories:** S2.1
**Depends on:** Phase 0 (model names), Phase 1 (install.yaml), Phase 2 (ALLOWED_HOSTS)
**Enables:** Phase 4 (skills can be added independently, but a working `--dry-run` is a useful checkpoint)
**Details:**
- Use `src/pathly_data/adapters/claude/_meta/*.yaml` as reference — copy the `name`, `description`, and `can_spawn`/`tools` fields verbatim; replace `model` with Antigravity equivalents.
- Model mapping (verify names against `agy models list` from Phase 0):

  | Role | Claude model | Antigravity model |
  |---|---|---|
  | architect | opus | `<pro-tier>` — e.g. `gemini-2.5-pro` |
  | builder | sonnet | `<flash-tier>` — e.g. `gemini-2.5-flash` |
  | designer | sonnet | `<flash-tier>` |
  | director | sonnet | `<flash-tier>` |
  | explorer | sonnet | `<flash-tier>` |
  | planner | sonnet | `<flash-tier>` |
  | po | sonnet | `<flash-tier>` |
  | reviewer | sonnet | `<flash-tier>` |
  | tester | sonnet | `<flash-tier>` |
  | quick | haiku | `<lite-tier>` — e.g. `gemini-2.5-flash-8b` |
  | scout | haiku | `<lite-tier>` |
  | web-researcher | sonnet | `<flash-tier>` |

- If Antigravity's agent YAML format does not support a `tools` field, omit it. If it does not support `can_spawn`, omit it. Emit only fields the format validates.
- The 11 files to create: `architect.yaml`, `builder.yaml`, `director.yaml`, `explorer.yaml`, `planner.yaml`, `po.yaml`, `quick.yaml`, `reviewer.yaml`, `scout.yaml`, `tester.yaml`, `web-researcher.yaml`
**Verify:** `python -m install_cli antigravity --dry-run 2>&1 | findstr /C:"Would write"` should show 11 agent file paths.

---

### Phase 4: Skill YAML files   ← Conversation: 3
**File:** `src/pathly_data/adapters/antigravity/_meta/<skill>_skill.yaml` × 19 — CREATE
**Done when:** exactly 19 `*_skill.yaml` files exist in `src/pathly_data/adapters/antigravity/_meta/`; `python -m install_cli antigravity --dry-run` lists 19 skill files under the skills destination; `python -m pytest tests/ -q` exits 0.
**Delivers stories:** S3.1
**Depends on:** Phase 3 (agents should exist first, but skills are independent of agents)
**Enables:** Phase 5 (full test coverage)
**Details:**
- Use `src/pathly_data/adapters/claude/_meta/*_skill.yaml` as reference — copy each file verbatim.
- The skills install as nested `<skill>/SKILL.md` (set `structure: nested` in `install.yaml`). The YAML `filename` field should be `<skill>/SKILL.md` if present in the claude adapter; otherwise the install CLI defaults correctly.
- The 19 files to create (matching the claude adapter exactly):
  `archive_skill.yaml`, `build_skill.yaml`, `end_skill.yaml`, `go_skill.yaml`, `help_skill.yaml`,
  `lessons_skill.yaml`, `meet_skill.yaml`, `pause_skill.yaml`, `pathly_skill.yaml`, `plan_skill.yaml`,
  `po_skill.yaml`, `prd-import_skill.yaml`, `retro_skill.yaml`, `review_skill.yaml`,
  `scout-path_skill.yaml`, `start_skill.yaml`, `storm_skill.yaml`, `test_skill.yaml`,
  `verify-state_skill.yaml`
- No Antigravity-specific changes to skill YAML content — the `stitch_skill` function handles frontmatter generation; skill bodies come from `core/skills/`.
**Verify:** `python -m install_cli antigravity --dry-run` and count skill lines; `python -m pytest tests/ -q`

---

### Phase 5: Test coverage   ← Conversation: 4
**File:** `tests/test_setup.py` and `tests/test_e2e_install.py` — MODIFY
**Done when:** `python -m pytest tests/ -q` exits 0 and includes at least 2 new passing tests asserting antigravity detection and dry-run behavior.
**Delivers stories:** S4.1
**Depends on:** Phases 1–4 (all adapter files must exist for e2e dry-run to succeed)
**Enables:** nothing (final phase)
**Details:**
- In `tests/test_setup.py`, add after the existing `test_host_markers_cover_all_supported_hosts` test:
  ```python
  def test_host_markers_cover_antigravity():
      assert "antigravity" in _HOST_MARKERS

  def test_detect_antigravity_when_dir_exists(tmp_path):
      agy_dir = tmp_path / ".gemini" / "antigravity-cli"
      agy_dir.mkdir(parents=True)
      with patch("install_cli.detect._HOST_MARKERS", {"antigravity": [agy_dir]}):
          result = detect_hosts()
      assert "antigravity" in result

  def test_detect_antigravity_when_dir_missing(tmp_path):
      with patch("install_cli.detect._HOST_MARKERS", {"antigravity": [tmp_path / "nonexistent"]}):
          result = detect_hosts()
      assert "antigravity" not in result
  ```
- In `tests/test_e2e_install.py`, add a `@pytest.mark.slow` test that:
  1. Creates `tmp_path / ".gemini" / "antigravity-cli"` so detection fires
  2. Calls `_run_install_cli(["antigravity", "--dry-run"], tmp_path)`
  3. Asserts `result.returncode == 0`
  4. Asserts `"[antigravity]"` in `result.stdout`
  5. Asserts `"Would write"` in `result.stdout`
- Pattern exactly mirrors the existing `test_dry_run_exits_0` test for claude.
**Verify:** `python -m pytest tests/test_setup.py tests/test_e2e_install.py -v`

---

## Key Decisions

- **Skills directory `~/.gemini/antigravity-cli/skills/` (not `~/.agents/skills/`):** Antigravity's global skills path mirrors Codex's `~/.agents/skills/` concept but under the Antigravity home. Using the Antigravity-specific path avoids collision with any Codex install on the same machine. Verify against `agy --help` or docs before finalizing.
- **No plugin registration step in v1:** Codex requires a `codex_plugin_config.py` marketplace registration. Antigravity's plugin registration mechanism is not fully documented in public sources. Deferring to a follow-up adapter — ship the skill/agent files first, add plugin registration once the API is confirmed.
- **Use `~/.gemini/antigravity-cli` as detection marker (not `~/.gemini`):** `~/.gemini/` may exist for unrelated Gemini API tooling. The `antigravity-cli` subdirectory is more specific and less likely to false-positive.
- **Model names are placeholders until Phase 0 pre-flight:** Do not hardcode model names before running `agy models list`. If the `agy` binary is unavailable during planning, document placeholder names in README.md with a TODO.
