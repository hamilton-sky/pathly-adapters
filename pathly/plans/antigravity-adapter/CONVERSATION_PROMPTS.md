---
name: Conversation Guide
---
# antigravity-adapter — Conversation Guide

Split into 4 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Infrastructure skeleton (Phases 0–2)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Read pathly/plans/antigravity-adapter/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-adapter Conversation 1 (Phases 0–2) from pathly/plans/antigravity-adapter/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `src/install_cli/orchestrate.py` — add "antigravity" to ALLOWED_HOSTS
- `src/install_cli/detect.py` — add "antigravity" to _HOST_MARKERS
- `src/pathly_data/adapters/antigravity/_meta/install.yaml` — CREATE
- `src/pathly_data/adapters/antigravity/README.md` — CREATE

**Phase 0 — Pre-flight (no file written):**
- Run `agy --version` or `where agy` to check if the agy CLI is installed. Record the result.
- If agy is present, run `agy models list` and record the pro-tier and flash-tier model names. You will use these in Conversation 2 agent YAMLs.
- If agy is absent, note it and use placeholder model names `gemini-2.5-pro` (pro-tier) and `gemini-2.5-flash` (flash-tier) with a TODO in README.md.
- Run `python -m pytest tests/ -q` and record any pre-existing failures as baseline. Do NOT fix them.

**Phase 1 — install.yaml + README:**
- Create `src/pathly_data/adapters/antigravity/_meta/install.yaml` with:
  ```
  host: antigravity
  destination: ~/.gemini/antigravity-cli/agents/
  skills:
    destination: ~/.gemini/antigravity-cli/skills/
    structure: nested
  templates:
    destination: ~/.gemini/antigravity-cli/plugins/pathly/templates
  telemetry: true
  ```
  If Phase 0 reveals different install paths from agy docs/help, use those instead.
- Create `src/pathly_data/adapters/antigravity/README.md` with: install instructions, agy binary install command (`irm https://antigravity.google/cli/install.ps1 | iex` on Windows), skills directory location, and model names used (with TODO if placeholders).

**Phase 2 — detect.py + orchestrate.py:**
- Read `src/install_cli/orchestrate.py`. Add `"antigravity"` to `ALLOWED_HOSTS`.
- Read `src/install_cli/detect.py`. Add to `_HOST_MARKERS`:
  ```python
  "antigravity": [
      Path.home() / ".gemini" / "antigravity-cli",
  ],
  ```
- Also check the comment in orchestrate.py: "Must stay in sync with detect_hosts()" — ensure both files are updated.

Architectural rules to observe:
- Do NOT touch core/ agents or skills — adapter is configuration only.
- Do NOT create agent or skill YAML files yet — those are Conversations 2 and 3.

Verify: `python -c "from install_cli.orchestrate import ALLOWED_HOSTS; assert 'antigravity' in ALLOWED_HOSTS, 'missing'" && python -m pytest tests/ -q`
After done, update pathly/plans/antigravity-adapter/PROGRESS.md Conv 1 phases to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `ALLOWED_HOSTS` contains `antigravity`; `_HOST_MARKERS` has an antigravity entry; `install.yaml` and `README.md` exist; all pre-existing tests still pass.
**Files touched:** `orchestrate.py`, `detect.py`, `_meta/install.yaml`, `README.md`

---

## Conversation 2: Agent YAML files (Phase 3)

**Stories delivered:** S2.1

**Prompt to paste:**
```
Read pathly/plans/antigravity-adapter/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-adapter Conversation 2 (Phase 3) from pathly/plans/antigravity-adapter/IMPLEMENTATION_PLAN.md.

**Before editing anything:**
- Glob `src/pathly_data/adapters/claude/_meta/*.yaml` to confirm the reference agent YAMLs exist (exclude `*_skill.yaml` files).
- Glob `src/pathly_data/adapters/antigravity/_meta/` to confirm install.yaml exists from Conversation 1.
- Check PROGRESS.md — Conv 1 must be DONE before starting.

**Codebase files this conversation touches:**
- `src/pathly_data/adapters/antigravity/_meta/<agent>.yaml` × 11 — CREATE

**Phase 3 — Agent YAML files:**
Create 11 agent YAML files in `src/pathly_data/adapters/antigravity/_meta/`. Use the corresponding claude adapter YAML as reference for `name`, `description`, `tools`, and `can_spawn` fields. Replace `model` with the Gemini model name recorded in Conversation 1 Phase 0.

Model mapping:
- architect → pro-tier (e.g. `gemini-2.5-pro`)
- builder, designer, director, explorer, planner, po, reviewer, tester, web-researcher → flash-tier (e.g. `gemini-2.5-flash`)
- quick, scout → lite/flash-tier (e.g. `gemini-2.5-flash` or lighter if available)

If Antigravity agent YAML format does not support `tools` or `can_spawn`, omit those fields. Emit only fields the format validates (verify by reading the claude YAML structure and checking if those fields are used in stitch_agent in src/install_cli/stitch.py).

Files to create:
architect.yaml, builder.yaml, director.yaml, explorer.yaml, planner.yaml, po.yaml,
quick.yaml, reviewer.yaml, scout.yaml, tester.yaml, web-researcher.yaml

Architectural rules to observe:
- Do NOT create skill YAMLs yet — that is Conversation 3.
- Do NOT modify core/ agent markdown — adapter is configuration only.

Verify: `python -m install_cli antigravity --dry-run` — count the agent files listed under "Would write to". Expect 11 agent .md files.
Also run: `python -m pytest tests/ -q`
After done, update pathly/plans/antigravity-adapter/PROGRESS.md Conv 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 11 agent YAML files in `_meta/`; `--dry-run` lists 11 agents; tests pass.
**Files touched:** `src/pathly_data/adapters/antigravity/_meta/*.yaml` (×11)

---

## Conversation 3: Skill YAML files (Phase 4)

**Stories delivered:** S3.1

**Prompt to paste:**
```
Read pathly/plans/antigravity-adapter/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-adapter Conversation 3 (Phase 4) from pathly/plans/antigravity-adapter/IMPLEMENTATION_PLAN.md.

**Before editing anything:**
- Glob `src/pathly_data/adapters/claude/_meta/*_skill.yaml` to get the reference list.
- Glob `src/pathly_data/adapters/antigravity/_meta/` to confirm agent YAMLs from Conversation 2 exist.
- Check PROGRESS.md — Conv 2 must be DONE before starting.

**Codebase files this conversation touches:**
- `src/pathly_data/adapters/antigravity/_meta/*_skill.yaml` × 19 — CREATE

**Phase 4 — Skill YAML files:**
Create 19 skill YAML files in `src/pathly_data/adapters/antigravity/_meta/` by copying each corresponding file from `src/pathly_data/adapters/claude/_meta/`. The content is identical — no Antigravity-specific changes are needed because `stitch_skill` in `src/install_cli/stitch.py` handles frontmatter and the skill body comes from `core/skills/`.

Files to create (matching claude adapter exactly):
archive_skill.yaml, build_skill.yaml, end_skill.yaml, go_skill.yaml, help_skill.yaml,
lessons_skill.yaml, meet_skill.yaml, pause_skill.yaml, pathly_skill.yaml, plan_skill.yaml,
po_skill.yaml, prd-import_skill.yaml, retro_skill.yaml, review_skill.yaml,
scout-path_skill.yaml, start_skill.yaml, storm_skill.yaml, test_skill.yaml,
verify-state_skill.yaml

Architectural rules to observe:
- Do NOT modify core/ skill markdown.
- Do NOT create any new file types — only `*_skill.yaml` files in `_meta/`.

Verify: `python -m install_cli antigravity --dry-run` — count skill files listed under skills destination. Expect 19 skills.
Also run: `python -m pytest tests/ -q`
After the verify command passes, write `pathly/plans/antigravity-adapter/VERIFY.md` with first line `RESULT: PASS` and a one-line summary of the dry-run output.
After done, update pathly/plans/antigravity-adapter/PROGRESS.md Conv 3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 19 skill YAMLs in `_meta/`; `--dry-run` lists 19 skills; tests pass; `VERIFY.md` written.
**Files touched:** `src/pathly_data/adapters/antigravity/_meta/*_skill.yaml` (×19)

---

## Conversation 4: Test coverage (Phase 5)

**Stories delivered:** S4.1

**Prompt to paste:**
```
Read pathly/plans/antigravity-adapter/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement antigravity-adapter Conversation 4 (Phase 5) from pathly/plans/antigravity-adapter/IMPLEMENTATION_PLAN.md.

**Before editing anything:**
- Read `tests/test_setup.py` to understand the existing structure and imports.
- Read `tests/test_e2e_install.py` to understand the existing _run_install_cli helper pattern.
- Check PROGRESS.md — Conv 3 must be DONE before starting.

**Codebase files this conversation touches:**
- `tests/test_setup.py` — MODIFY (add antigravity detection tests)
- `tests/test_e2e_install.py` — MODIFY (add antigravity dry-run e2e test)

**Phase 5 — Test coverage:**
In `tests/test_setup.py`, add three tests after the existing host marker tests:
1. `test_host_markers_cover_antigravity` — asserts `"antigravity"` in `_HOST_MARKERS`
2. `test_detect_antigravity_when_dir_exists(tmp_path)` — creates the marker dir, patches `_HOST_MARKERS`, asserts detection returns `True`
3. `test_detect_antigravity_when_dir_missing(tmp_path)` — patches `_HOST_MARKERS` with a nonexistent path, asserts `False`

In `tests/test_e2e_install.py`, add a `@pytest.mark.slow` test `test_antigravity_dry_run_exits_0(tmp_path)`:
- Create `tmp_path / ".gemini" / "antigravity-cli"` (mirrors the way the claude test creates `tmp_path / ".claude"`)
- Call `_run_install_cli(["antigravity", "--dry-run"], tmp_path)`
- Assert `result.returncode == 0`
- Assert `"[antigravity]"` in `result.stdout`
- Assert `"Would write"` in `result.stdout`

Architectural rules to observe:
- Do NOT modify any adapter files — tests only.
- Mirror the existing test patterns exactly (same imports, same helper functions).

Verify: `python -m pytest tests/test_setup.py tests/test_e2e_install.py -v`
After done, update pathly/plans/antigravity-adapter/PROGRESS.md Conv 4 to DONE and Status to COMPLETE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** All new tests pass; full test suite still green.
**Files touched:** `tests/test_setup.py`, `tests/test_e2e_install.py`
