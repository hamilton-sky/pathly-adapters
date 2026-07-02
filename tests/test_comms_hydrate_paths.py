"""Regression tests for CT5 — the authoritative-channel 'section not found' bug.

context_refs store artifact paths as full repo-relative strings
(``pathly/features/<f>/PROPOSAL.md``), and the storage-restructure moved feature homes
out of ``pathly/plans/``. Two defects made the 📎 Referenced (authoritative) channel emit
"section not found":
  1. ``safe_plan_path`` rejected any artifact containing '/' and only looked under
     ``pathly/plans/<scope>/`` → ``safe_artifact_path`` supersedes it.
  2. ``find_or_create_artifact_by_path`` created sentinel rows only for plans/goals paths
     → features/ (and project/) added to the allowlist.
"""

from __future__ import annotations

from pathly_orchestrator.runner.hydrate_helpers import safe_artifact_path


def _mk(tmp_path, *parts, text="# Doc\n\nbody\n"):
    p = tmp_path.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_full_repo_relative_ref_resolves(tmp_path):
    _mk(tmp_path, "pathly", "features", "feat", "PROPOSAL.md")
    got = safe_artifact_path("feat", "pathly/features/feat/PROPOSAL.md", str(tmp_path))
    assert got is not None
    assert got.replace("\\", "/").endswith("pathly/features/feat/PROPOSAL.md")


def test_basename_prefers_features_home(tmp_path):
    _mk(tmp_path, "pathly", "features", "feat", "DOC.md")
    got = safe_artifact_path("feat", "DOC.md", str(tmp_path))
    assert got is not None and "features" in got.replace("\\", "/")


def test_basename_falls_back_to_legacy_plans(tmp_path):
    _mk(tmp_path, "pathly", "plans", "feat", "OLD.md")
    got = safe_artifact_path("feat", "OLD.md", str(tmp_path))
    assert got is not None and "plans" in got.replace("\\", "/")


def test_rejects_traversal_and_absolute(tmp_path):
    root = str(tmp_path)
    assert safe_artifact_path("feat", "../../../etc/passwd", root) is None
    assert safe_artifact_path("feat", "pathly/../../secrets.md", root) is None
    assert safe_artifact_path("feat", "/etc/passwd", root) is None
    assert safe_artifact_path("feat", "C:/Windows/system.ini", root) is None


def test_hydrate_whole_file_for_features_ref(tmp_path):
    """End-to-end: a bare (no-anchor) features/ ref hydrates whole-file at 200."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.hydrate import hydrate_section

    _mk(tmp_path, "pathly", "features", "feat", "SPEC.md", text="# Spec\n\nauthoritative body\n")
    res = hydrate_section(
        get_db(),
        scope="feat",
        artifact="pathly/features/feat/SPEC.md",
        anchor=None,
        project_root=str(tmp_path),
    )
    assert res["status"] == 200, res["body"]
    assert "authoritative body" in res["body"]["text"]


def test_find_or_create_accepts_features_path(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import find_or_create_artifact_by_path

    p = _mk(tmp_path, "pathly", "features", "feat", "A.md")
    row = find_or_create_artifact_by_path(get_db(), "feat", str(p))
    assert row is not None and row["type"] == "md"
