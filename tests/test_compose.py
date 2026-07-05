"""Tests for the skill-fragment composition resolver + validator.

Two delivery modes share one resolver (compose_skill); the validator is the
loud build-time gate. Conv 2 ships the engine as a behaviour-preserving no-op:
while the real manifest's `skills:` map is empty, every skill composes
byte-identical to its raw body.
"""

from pathlib import Path

import pytest

from pathly_orchestrator.compose import (
    adapter_caps_for,
    compose_skill,
    load_manifest,
    resolve_block,
    validate_composition,
)

# A distinctive line from fragments/spawn-rules.md — used to assert gating.
_SPAWN_RULES_MARKER = "## Sub-agent spawning rules"

_SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

# The five shared-section H2 headings; each must appear exactly once in a composed skill.
_SHARED_SECTIONS = [
    "## Live progress logging",
    "## Completion report",
    "## Scout choreography",
    "## Feedback protocol",
    "## Sub-agent spawning rules",
]


# ── Inert-seam: real (empty) manifest is a no-op ────────────────────────────


@pytest.mark.parametrize(
    "skill", ["development/fix", "development/quick-fix", "development/commit"]
)
def test_unconverted_skill_composes_raw_body(skill):
    """A skill ABSENT from the manifest composes byte-identical to its raw body.

    These development/* skills are not in the composition manifest, so the
    resolver must return their raw body unchanged — the inert-seam guarantee.
    (design/debug/explore were moved into the manifest for Gap 1 board write-back.)
    """
    from pathly_orchestrator.compose import _read_skill_body

    raw = _read_skill_body(skill)
    assert compose_skill(skill, "claude") == raw


def test_real_manifest_validates():
    """The shipped manifest must always pass its own validator."""
    validate_composition()  # raises on any problem


# ── Resolver: assembly + adapter gating ─────────────────────────────────────


def _synthetic_manifest(fragments):
    return {
        "version": 1,
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {"team/build": {"fragments": fragments}},
    }


def test_listed_skill_appends_fragment():
    manifest = _synthetic_manifest(["spawn-rules"])
    out = compose_skill("team/build", {"can_spawn": True}, manifest=manifest)
    assert _SPAWN_RULES_MARKER in out


def test_gated_fragment_kept_when_capability_true():
    manifest = _synthetic_manifest([{"name": "spawn-rules", "requires": "can_spawn"}])
    out = compose_skill("team/build", {"can_spawn": True}, manifest=manifest)
    assert _SPAWN_RULES_MARKER in out


def test_gated_fragment_dropped_when_capability_false():
    manifest = _synthetic_manifest([{"name": "spawn-rules", "requires": "can_spawn"}])
    out = compose_skill("team/build", {"can_spawn": False}, manifest=manifest)
    assert _SPAWN_RULES_MARKER not in out


def test_defaults_only_when_fragments_empty():
    manifest = {
        "version": 1,
        "fragments_dir": "fragments",
        "defaults": ["completion-report"],
        "skills": {"team/build": {"fragments": []}},
    }
    out = compose_skill("team/build", {}, manifest=manifest)
    from pathly_orchestrator.compose import _read_fragment

    assert _read_fragment("fragments", "completion-report").strip() in out


def test_adapter_string_resolves_to_caps():
    """compose_skill accepts an adapter-name string, not just a caps dict."""
    manifest = _synthetic_manifest([{"name": "spawn-rules", "requires": "can_spawn"}])
    # claude has can_spawn=True today, so the gated fragment stays.
    out = compose_skill("team/build", "claude", manifest=manifest)
    assert _SPAWN_RULES_MARKER in out


# ── adapter_caps_for ────────────────────────────────────────────────────────


def test_adapter_caps_for_claude_can_spawn():
    assert adapter_caps_for("claude") == {"can_spawn": True}


def test_adapter_caps_for_unknown_raises():
    with pytest.raises(ValueError):
        adapter_caps_for("nonsuch")


# ── Validator: rejects malformed manifests ──────────────────────────────────


def test_validator_rejects_unknown_fragment():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {"team/build": {"fragments": ["no-such-fragment"]}},
    }
    with pytest.raises(ValueError, match="unknown fragment"):
        validate_composition(manifest)


def test_validator_rejects_unknown_skill():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {"team/does-not-exist": {"fragments": ["feedback-protocol"]}},
    }
    with pytest.raises(ValueError, match="unknown skill"):
        validate_composition(manifest)


def test_validator_rejects_duplicate_include():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {
            "team/build": {"fragments": ["feedback-protocol", "feedback-protocol"]}
        },
    }
    with pytest.raises(ValueError, match="duplicate"):
        validate_composition(manifest)


def test_validator_rejects_duplicate_against_defaults():
    """A fragment in defaults AND a skill's own list is a duplicate include."""
    manifest = {
        "fragments_dir": "fragments",
        "defaults": ["feedback-protocol"],
        "skills": {"team/build": {"fragments": ["feedback-protocol"]}},
    }
    with pytest.raises(ValueError, match="duplicate"):
        validate_composition(manifest)


def test_validator_rejects_unknown_capability():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {
            "team/build": {
                "fragments": [{"name": "spawn-rules", "requires": "can_fly"}]
            }
        },
    }
    with pytest.raises(ValueError, match="unknown capability"):
        validate_composition(manifest)


def test_load_manifest_shape():
    manifest = load_manifest()
    assert "progress-logging" in [
        e if isinstance(e, str) else e.get("name") for e in manifest.get("defaults", [])
    ]


# ── Converted team/* family: golden snapshots + exactly-once guarantee ───────

_CONVERTED_TEAM_SKILLS = ["team/build", "team/review", "team/test", "team/design", "team/retro", "planning/plan"]


@pytest.mark.parametrize("skill", _CONVERTED_TEAM_SKILLS)
def test_team_skill_matches_golden_snapshot(skill):
    """Composed claude output must match the reviewed snapshot — fails on drift."""
    snap = _SNAPSHOT_DIR / (skill.replace("/", "__") + ".claude.md")
    assert snap.exists(), f"missing golden snapshot: {snap}"
    expected = snap.read_text(encoding="utf-8")
    assert compose_skill(skill, "claude") == expected


@pytest.mark.parametrize("skill", _CONVERTED_TEAM_SKILLS)
def test_team_skill_shared_sections_appear_at_most_once(skill):
    """No shared section may appear twice (no duplication between body and fragment)."""
    out = compose_skill(skill, "claude")
    for heading in _SHARED_SECTIONS:
        assert out.count(heading) <= 1, f"{skill}: {heading!r} duplicated"


def test_team_build_and_review_include_all_five_sections():
    """build/review compose every shared section exactly once (spawn-rules included)."""
    for skill in ("team/build", "team/review"):
        out = compose_skill(skill, "claude")
        for heading in _SHARED_SECTIONS:
            assert out.count(heading) == 1, f"{skill}: {heading!r} not exactly once"


def test_team_test_omits_spawn_rules():
    """team/test has no spawn-rules in its manifest entry."""
    out = compose_skill("team/test", "claude")
    assert _SPAWN_RULES_MARKER not in out
    for heading in _SHARED_SECTIONS:
        if heading != _SPAWN_RULES_MARKER:
            assert out.count(heading) == 1


def test_team_build_drops_spawn_rules_for_non_spawn_adapter():
    """A converted skill drops spawn-rules when the adapter can't spawn."""
    out = compose_skill("team/build", {"can_spawn": False})
    assert _SPAWN_RULES_MARKER not in out
    # the non-gated shared sections still compose in
    assert "## Feedback protocol" in out
    assert "## Scout choreography" in out


# ── Converted development/* family: golden snapshots + exactly-once guarantee ─

_CONVERTED_DEV_SKILLS = ["development/build", "development/review", "development/test"]


@pytest.mark.parametrize("skill", _CONVERTED_DEV_SKILLS)
def test_dev_skill_matches_golden_snapshot(skill):
    """Composed claude output must match the reviewed snapshot — fails on drift."""
    snap = _SNAPSHOT_DIR / (skill.replace("/", "__") + ".claude.md")
    assert snap.exists(), f"missing golden snapshot: {snap}"
    expected = snap.read_text(encoding="utf-8")
    assert compose_skill(skill, "claude") == expected


@pytest.mark.parametrize("skill", _CONVERTED_DEV_SKILLS)
def test_dev_skill_shared_sections_appear_at_most_once(skill):
    """No shared section may appear twice (no duplication between body and fragment)."""
    out = compose_skill(skill, "claude")
    for heading in _SHARED_SECTIONS:
        assert out.count(heading) <= 1, f"{skill}: {heading!r} duplicated"


@pytest.mark.parametrize("skill", ["development/drain-dag", "development/execute-task"])
def test_task_executors_include_task_progress_fragment(skill):
    """Both task executors — the single `drain-dag` agent and the loop `execute-task` agent —
    must compose the `task-progress` fragment so a headless run posts a ▶/✔ status per task.
    `comms-post` mirrors findings and `progress-logging` marks pipeline phases; neither covers
    per-task status, so without this a single/loop agent shows no mid-run progress at all."""
    out = compose_skill(skill, "claude")
    assert "Task progress (board status)" in out, f"{skill} is missing the task-progress fragment"
    assert "▶ Started" in out and "✔ Done" in out, f"{skill} is missing the status markers"
    # completion-report must remain LAST (it owns the "AGENT_DONE is your final act" rule).
    assert out.index("Task progress (board status)") < out.index("Completion report (AGENT_DONE)"), (
        f"{skill}: task-progress must compose BEFORE completion-report"
    )


def test_dev_build_includes_completion_scout_and_spawn():
    """development/build composes completion-report + scout-choreography + spawn-rules.

    It is the only development skill that records BUILD_START, so it keeps the
    completion-report fragment. It has no feedback-protocol.
    """
    out = compose_skill("development/build", "claude")
    assert out.count("## Completion report") == 1
    assert out.count("## Scout choreography") == 1
    assert out.count(_SPAWN_RULES_MARKER) == 1
    assert out.count("## Feedback protocol") == 0


def test_dev_review_includes_scout_and_spawn_only():
    """development/review keeps its own PASS/FAIL exit — scout + spawn-rules, no completion-report."""
    out = compose_skill("development/review", "claude")
    assert out.count("## Scout choreography") == 1
    assert out.count(_SPAWN_RULES_MARKER) == 1
    assert out.count("## Completion report") == 0
    assert out.count("## Feedback protocol") == 0


def test_dev_test_includes_scout_only():
    """development/test composes scout-choreography only — no spawn-rules, no completion-report."""
    out = compose_skill("development/test", "claude")
    assert out.count("## Scout choreography") == 1
    assert _SPAWN_RULES_MARKER not in out
    assert out.count("## Completion report") == 0
    assert out.count("## Feedback protocol") == 0


def test_dev_build_drops_spawn_rules_for_non_spawn_adapter():
    """development/build drops spawn-rules when the adapter can't spawn, keeps the rest."""
    out = compose_skill("development/build", {"can_spawn": False})
    assert _SPAWN_RULES_MARKER not in out
    assert "## Completion report" in out
    assert "## Scout choreography" in out


# ── Block resolver tests ──────────────────────────────────────────────────────


def test_valid_default_blocks_pass_validation():
    """The shipped manifest's blocks (full-build, lite-build, review-strict) are all valid."""
    validate_composition()  # raises on any problem


def test_block_unknown_fragment_raises():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {},
        "blocks": {"bad": ["nonexistent-fragment"]},
    }
    with pytest.raises(ValueError, match="nonexistent-fragment"):
        validate_composition(manifest)


def test_block_unknown_requires_capability_raises():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {},
        "blocks": {"bad": [{"name": "completion-report", "requires": "bad-cap"}]},
    }
    with pytest.raises(ValueError, match="bad-cap"):
        validate_composition(manifest)


def test_block_duplicate_fragment_raises():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {},
        "blocks": {"bad": ["completion-report", "completion-report"]},
    }
    with pytest.raises(ValueError, match="duplicate|completion-report"):
        validate_composition(manifest)


def test_task_dag_post_block_retired():
    """The task-dag-post stopgap is gone — `planning/plan` is the real decomposer now
    (it derives context_refs + depends_on). The consultation-plan block must not exist."""
    with pytest.raises(KeyError):
        resolve_block("consultation-plan", "claude")
    # planning/plan still composes cleanly (it stays the terminal planner for all decompose tiers).
    assert "context_refs" in compose_skill("planning/plan", "claude")


def test_manifest_without_blocks_key_passes_validation():
    manifest = {
        "fragments_dir": "fragments",
        "defaults": [],
        "skills": {},
    }
    validate_composition(manifest)  # no exception expected


def test_resolve_block_gated_fragment_dropped_when_cap_false():
    """full-build has spawn-rules gated on can_spawn; passing empty caps drops it."""
    result = resolve_block("full-build", {})
    spawn_rules_text = _SPAWN_RULES_MARKER
    assert all(spawn_rules_text not in item for item in result)


def test_resolve_block_unknown_block_raises_key_error():
    with pytest.raises(KeyError):
        resolve_block("no-such-block", {})


def test_user_block_overrides_core_block():
    """A user_blocks entry for an existing block name replaces it entirely."""
    user_blocks = {"full-build": ["completion-report"]}
    result = resolve_block("full-build", {}, user_blocks=user_blocks)
    assert len(result) == 1


def test_build_adapter_caps_merges_goal_context():
    from pathly_orchestrator.skills.compose import build_adapter_caps
    caps = build_adapter_caps("claude", goal_id="g1", executor="loop", kind="dag")
    assert caps["goal_id"] == "g1"
    assert caps["executor"] == "loop"
    assert caps["kind"] == "dag"
    # can_spawn from the adapter
    assert isinstance(caps.get("can_spawn"), bool)


def test_goal_id_gate_known_capability():
    """goal_id is a known capability and gates fragments correctly."""
    from pathly_orchestrator.skills.compose import (
        _KNOWN_CAPABILITIES,
        build_adapter_caps,
    )
    assert "goal_id" in _KNOWN_CAPABILITIES

    # With goal_id — a gated fragment would be kept
    caps_with = build_adapter_caps("claude", goal_id="g1")
    assert caps_with.get("goal_id") == "g1"  # truthy → gated fragment kept

    # Without goal_id — gated fragment dropped
    caps_without = build_adapter_caps("claude", goal_id="")
    assert not caps_without.get("goal_id")  # falsy → gated fragment dropped


def test_dag_sketch_composes_task_post_and_completion():
    from pathly_orchestrator.skills.compose import compose_skill, build_adapter_caps

    # With goal_id — both gated fragments included
    out = compose_skill("planning/dag-sketch", build_adapter_caps("claude", goal_id="g1"))
    assert "## Posting the task DAG to the Comms Board" in out
    assert "## Reading the board before you decompose" in out
    assert "## Completion report" in out

    # Without goal_id — gated fragments dropped but completion-report stays
    out_no_goal = compose_skill("planning/dag-sketch", build_adapter_caps("claude"))
    assert "## Posting the task DAG to the Comms Board" not in out_no_goal
    assert "## Reading the board before you decompose" not in out_no_goal
    assert "## Completion report" in out_no_goal


def test_plan_composes_task_dag_post_before_completion():
    """planning/plan includes task-dag-post before completion-report when goal_id set."""
    from pathly_orchestrator.skills.compose import compose_skill, build_adapter_caps

    # With goal_id — task-dag-post fragment included
    out = compose_skill("planning/plan", build_adapter_caps("claude", goal_id="g1"))
    assert "## Posting the task DAG to the Comms Board" in out
    task_idx = out.index("## Posting the task DAG to the Comms Board")
    completion_idx = out.index("## Completion report")
    assert task_idx < completion_idx, "task-dag-post must appear before completion-report"


# ── artifact-manifest + artifact-register tests ───────────────────────────────


def test_artifact_manifest_loads():
    from pathly_orchestrator.skills.compose import load_artifact_manifest
    m = load_artifact_manifest()
    assert m["version"] == 1
    assert "planner" in m["roles"]
    assert m["roles"]["designer"]["gate"] == "## Design System Output"


def test_manifest_role_file_override():
    from pathly_orchestrator.skills.compose import manifest_role_file
    assert manifest_role_file("planner", "planning/dag-sketch") == ("DAG_PLAN.md", "## Tasks")
    assert manifest_role_file("planner") == ("IMPLEMENTATION_PLAN.md", "## Phase")
    assert manifest_role_file("designer") == ("DESIGN.md", "## Design System Output")
    assert manifest_role_file("nonexistent-role") is None


def test_artifact_register_composed():
    out = compose_skill("team/build", "claude")
    assert "## Registering your output artifact" in out


def test_artifact_register_not_in_po():
    out = compose_skill("planning/po", "claude")
    assert "## Registering your output artifact" not in out


def test_artifact_register_never_last():
    """No ordering-invariant skill may end on artifact-register."""
    for skill in ("team/build", "team/review", "team/test", "team/design",
                  "team/retro", "planning/plan"):
        out = compose_skill(skill, "claude").rstrip()
        # the artifact-register section must not be the final section
        reg = "## Registering your output artifact"
        assert reg in out
        tail = out[out.index(reg) + len(reg):]
        assert tail.lstrip().count("## ") >= 1 or "comms-post" in tail.lower() or "Completion" in tail, \
            f"{skill}: artifact-register appears to be the last section"
