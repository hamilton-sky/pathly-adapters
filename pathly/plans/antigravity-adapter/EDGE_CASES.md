---
name: Edge Cases
---
# antigravity-adapter — Edge Cases

## EC-1: `agy` binary not installed
**Trigger:** Developer runs Phase 0 and `where agy` returns nothing.
**Risk:** Agent YAML files written with wrong or guessed model names.
**Mitigation:** Document placeholder model names in `README.md` with a TODO. Use `gemini-2.5-pro` and `gemini-2.5-flash` as placeholders. The builder must explicitly note these are unverified.
**Test:** Not automated — human review of README.md TODO during review phase.

## EC-2: `~/.gemini/` exists but `antigravity-cli/` does not
**Trigger:** Machine has Gemini CLI or other Google tooling that created `~/.gemini/` but Antigravity is not installed.
**Risk:** `detect_hosts()` false-positives and includes `antigravity` in auto-detection.
**Mitigation:** Use `~/.gemini/antigravity-cli` (not `~/.gemini`) as the detection marker — the `antigravity-cli` subdirectory is created only by the `agy` installer.
**Test:** `test_detect_antigravity_when_dir_missing` covers the no-marker case.

## EC-3: Install paths differ from plan assumptions
**Trigger:** `agy` docs or `agy --help` reveal that global agents are at a different path than `~/.gemini/antigravity-cli/agents/`.
**Risk:** Deployed files land in a location `agy` doesn't read.
**Mitigation:** Phase 0 pre-flight explicitly checks `agy --help` for install paths before writing `install.yaml`. If paths differ, update `install.yaml` accordingly.
**Test:** `test_antigravity_dry_run_exits_0` validates the dry-run output paths are consistent with install.yaml; human verification that `agy` reads from the stated path.

## EC-4: Antigravity agent YAML format rejects unknown fields
**Trigger:** Claude adapter YAML files include `tools` and `can_spawn` fields that Antigravity's agent parser doesn't recognize.
**Risk:** `agy` refuses to load agents with unknown fields.
**Mitigation:** `stitch_agent` in `stitch.py` only emits `tools`/`can_spawn` when present in meta YAML. Only include fields that Antigravity's format accepts. If uncertain, omit optional fields.
**Test:** `pathly-setup antigravity --dry-run` must exit 0 — any YAML generation errors surface there.

## EC-5: Skill name collision with existing `agy` skills
**Trigger:** User has a skill named `pathly-go` or `pathly-build` from another source.
**Risk:** The install CLI overwrites a user-owned skill file.
**Mitigation:** The `materialize()` function tracks ownership via `.pathly-manifest.json`. It will not overwrite files not in the manifest unless `--force` is used. Users are protected unless they explicitly pass `--force`.
**Test:** Covered by existing `test_manifests.py` — no new test needed.

## EC-6: Existing `python -m pytest tests/ -q` failures at baseline
**Trigger:** Pre-existing test failures exist before this feature starts.
**Risk:** Builder mistakes pre-existing failures for newly introduced failures.
**Mitigation:** Phase 0 records the baseline failure count. Conversations 1–4 are only responsible for not introducing *new* failures. Pre-existing failures are out of scope.
**Test:** Builder documents baseline in PROGRESS.md before starting Conv 1.

## EC-7: `pathly-setup` (no args) auto-detects both claude and antigravity
**Trigger:** User has both `~/.claude/` and `~/.gemini/antigravity-cli/` installed.
**Risk:** Setup runs for both hosts simultaneously; if one fails it may mask the other.
**Mitigation:** The `_run_host()` loop in `orchestrate.py` already handles multiple detected hosts with independent error reporting. No change needed — this is existing behaviour.
**Test:** Not a regression risk.
