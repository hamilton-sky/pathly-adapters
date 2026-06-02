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

@pytest.mark.parametrize("skill", ["development/design", "development/debug", "development/explore"])
def test_unconverted_skill_composes_raw_body(skill):
    """A skill ABSENT from the manifest composes byte-identical to its raw body.

    These development/* skills are not in the composition manifest, so the
    resolver must return their raw body unchanged — the inert-seam guarantee.
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
            "team/build": {"fragments": [{"name": "spawn-rules", "requires": "can_fly"}]}
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

_CONVERTED_TEAM_SKILLS = ["team/build", "team/review", "team/test"]


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
