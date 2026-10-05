"""Artifact-presence gates — ``require_artifact`` and ``verify_gate``.

Both are SELF-REPORT gates: they check that an agent wrote a file (and, for
``verify_gate``, a marker on its first line). They prove an agent *claimed* a result,
never that the claim is true — see ``command.py`` for the executed counterpart.
"""

from __future__ import annotations

from pathlib import Path

from ._helpers import gate_failed


def _verify_passed(path: Path, marker: str) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = text.splitlines()
    return bool(lines) and lines[0].strip() == marker


def check_require_artifact(
    gate: dict, storage_path: Path, prev_state: str, next_state: str, **_: object
) -> dict | None:
    artifact_path = storage_path / gate["artifact"]
    if artifact_path.exists():
        return None
    return gate_failed(
        storage_path,
        gate,
        "require_artifact",
        prev_state,
        next_state,
        f"Required artifact missing: {gate['artifact']}",
    )


def check_verify_gate(
    gate: dict, storage_path: Path, prev_state: str, next_state: str, **_: object
) -> dict | None:
    artifact_path = storage_path / gate["artifact"]
    marker = gate["pass_marker"]
    if _verify_passed(artifact_path, marker):
        return None
    reason = (
        f"VERIFY gate failed: `{gate['artifact']}` is missing or its first line "
        f"is not exactly {marker!r}.\n\n"
        f"**Action required:** Write `{storage_path / gate['artifact']}` "
        f"so that line 1 is exactly:\n\n"
        f"```\n{marker}\n```\n\n"
        f"No YAML frontmatter, no blank lines before it."
    )
    return gate_failed(
        storage_path, gate, "verify_gate", prev_state, next_state, reason
    )
