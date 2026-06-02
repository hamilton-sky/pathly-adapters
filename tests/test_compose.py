"""Tests for the skill-fragment composition resolver + validator.

Two delivery modes share one resolver (compose_skill); the validator is the
loud build-time gate. Conv 2 ships the engine as a behaviour-preserving no-op:
while the real manifest's `skills:` map is empty, every skill composes
byte-identical to its raw body.
"""

import pytest

from pathly_orchestrator.compose import (
    adapter_caps_for,
    compose_skill,
    load_manifest,
    validate_composition,
)

# A distinctive line from fragments/spawn-rules.md — used to assert gating.
_SPAWN_RULES_MARKER = "## Sub-agent spawning rules"


# ── Inert-seam: real (empty) manifest is a no-op ────────────────────────────

@pytest.mark.parametrize("skill", ["team/build", "development/build"])
def test_empty_manifest_composes_raw_body(skill):
    """With `skills: {}`, every skill composes byte-identical to its raw body."""
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
    assert manifest.get("skills") == {}, "skills map must stay empty until Conv 3"
    assert "progress-logging" in [
        e if isinstance(e, str) else e.get("name") for e in manifest.get("defaults", [])
    ]
