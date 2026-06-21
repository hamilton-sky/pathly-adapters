"""Regression tests for three confirmed defects fixed in Phase 3 comms-board context-retrieval.

FIX 1 — path traversal via unvalidated scope/artifact (BLOCKER/security)
FIX 2 — stale-index wipe when only mtime moved (MAJOR/correctness)
FIX 3 — duplicate explicit anchors cause UNIQUE violation (MINOR/robustness)
"""

from __future__ import annotations

import json
import os
import pathlib
import time

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_async(monkeypatch):
    """Stub async indexing so tests stay synchronous."""
    try:
        import pathly_orchestrator.runner.embeddings as _emb_mod
        monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)
        monkeypatch.setattr(_emb_mod, "embed", lambda text: None)
    except Exception:
        pass
    try:
        import pathly_orchestrator.runner.hydrate as _hyd_mod
        monkeypatch.setattr(_hyd_mod, "index_artifact_async", lambda *a, **k: None)
    except Exception:
        pass


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


@pytest.fixture()
def plan_dir(tmp_path):
    """Create pathly/plans/<scope>/ and return (base, scope, plan_root)."""
    scope = "fix-regression-test"
    plan_root = tmp_path / "pathly" / "plans" / scope
    plan_root.mkdir(parents=True)
    return tmp_path, scope, plan_root


# ---------------------------------------------------------------------------
# FIX 1 — safe_plan_path validator
# ---------------------------------------------------------------------------


class TestSafePlanPath:
    """Unit tests for safe_plan_path() — must fail without the fix."""

    def test_dotdot_scope_returns_none(self, tmp_path):
        """A traversal scope like '../../etc' must return None."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("../../etc", "file.md", str(tmp_path))
        assert result is None

    def test_slash_in_scope_returns_none(self, tmp_path):
        """A scope containing a slash ('a/b') must return None."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("a/b", "file.md", str(tmp_path))
        assert result is None

    def test_dotdot_artifact_returns_none(self, tmp_path):
        """An artifact like '../x.md' must return None."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("my-scope", "../x.md", str(tmp_path))
        assert result is None

    def test_absolute_scope_returns_none(self, tmp_path):
        """An absolute scope path must return None."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("/etc", "file.md", str(tmp_path))
        assert result is None

    def test_absolute_artifact_returns_none(self, tmp_path):
        """An absolute artifact path must return None."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("my-scope", "/etc/passwd", str(tmp_path))
        assert result is None

    def test_no_project_root_returns_none(self):
        """When project_root is falsy, safe_plan_path must return None."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        assert safe_plan_path("my-scope", "file.md", None) is None
        assert safe_plan_path("my-scope", "file.md", "") is None

    def test_clean_inputs_return_path(self, tmp_path):
        """Clean scope + artifact returns the expected absolute path."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("my-feature", "PLAN.md", str(tmp_path))
        assert result is not None
        expected = os.path.realpath(
            os.path.join(str(tmp_path), "pathly", "plans", "my-feature", "PLAN.md")
        )
        assert result == expected

    def test_backslash_in_artifact_returns_none(self, tmp_path):
        """A backslash in artifact must be rejected."""
        from pathly_orchestrator.runner.hydrate import safe_plan_path

        result = safe_plan_path("my-scope", "sub\\file.md", str(tmp_path))
        assert result is None


class TestFix1Integration:
    """Integration tests: malicious scope must not create out-of-tree sentinel rows."""

    def test_post_with_malicious_scope_does_not_create_outtree_row(
        self, client, conn, tmp_path
    ):
        """A /comms/post with a traversal scope in context_refs must NOT create
        a comms_artifacts row with a path outside the plan tree."""
        scope = "safe-scope"
        plan_root = tmp_path / "pathly" / "plans" / scope
        plan_root.mkdir(parents=True)

        # craft a ref with a malicious scope embedded in the artifact name
        # (the validate-at-write must call safe_plan_path and skip this ref)
        r = client.post(
            "/comms/post",
            json={
                "feature": scope,
                "from": "builder",
                "type": "nudge",
                "text": "test traversal guard",
                "board": "feature",
                "scope": scope,
                "context_refs": [
                    {"artifact": "../../etc/passwd", "anchor": "intro"}
                ],
                "project_root": str(tmp_path),
            },
        )
        # The post should succeed (best-effort — never fails the post)
        assert r.status_code == 200, r.data

        # Verify no comms_artifacts row points outside the plan tree
        rows = conn.execute(
            "SELECT path FROM comms_artifacts"
        ).fetchall()
        for row in rows:
            path_val = row["path"] or ""
            norm = path_val.replace("\\", "/")
            assert "/pathly/plans/" in norm or path_val == "", (
                f"Sentinel row with out-of-tree path created: {path_val}"
            )

    def test_section_endpoint_traversal_scope_returns_400(self, client, plan_dir, monkeypatch):
        """A /section request with a traversal scope must return 400 path_out_of_scope."""
        base, scope, plan_root = plan_dir

        monkeypatch.setattr(
            "pathly_orchestrator.runner.hydrate._resolve_plan_root",
            lambda sc, pr=None: str(plan_root),
        )

        r = client.get(
            "/comms/artifacts/section",
            query_string={
                "scope": "../../etc",
                "artifact": "passwd",
                "anchor": "intro",
                "project_root": str(base),
            },
        )
        assert r.status_code == 400, r.data
        body = json.loads(r.data)
        assert body["error"] == "path_out_of_scope"


# ---------------------------------------------------------------------------
# FIX 2 — stale-index wipe on mtime-only change
# ---------------------------------------------------------------------------


class TestFix2StaleIndexWipe:
    """FIX 2: bumping mtime without changing content must NOT wipe the index."""

    def test_mtime_bump_preserves_section_index(self, plan_dir, monkeypatch):
        """After mtime-bump (same content), get_artifact_sections still returns rows."""
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import get_artifact_sections
        from pathly_orchestrator.runner.hydrate import ensure_indexed

        base, scope, plan_root = plan_dir
        content = "## Phase 1\nbody content here\n## Phase 2\nmore body\n"
        md_path = plan_root / "MTIME_TEST.md"
        md_path.write_text(content, encoding="utf-8")
        path_str = str(md_path)

        db = get_db()

        # First index — builds section rows
        result1 = ensure_indexed(db, scope, path_str, str(base))
        assert result1["ok"] is True
        assert result1.get("stale_rebuilt") is True

        artifact_id = result1["artifact_id"]
        sections_before = get_artifact_sections(db, artifact_id)
        assert len(sections_before) == 2, "expected two sections after first index"

        # Bump mtime without changing content (re-write identical bytes then utime)
        md_path.write_bytes(md_path.read_bytes())
        # Force mtime to be detectably different by advancing it 2 seconds
        new_mtime = md_path.stat().st_mtime + 2.0
        os.utime(str(md_path), (new_mtime, new_mtime))

        # Second ensure_indexed — hash is the same, only mtime changed
        result2 = ensure_indexed(db, scope, path_str, str(base))
        assert result2["ok"] is True
        # stale_rebuilt should be False — it was a mtime-only update
        assert result2.get("stale_rebuilt") is False

        # The section rows must still be present (not wiped)
        sections_after = get_artifact_sections(db, artifact_id)
        assert len(sections_after) == 2, (
            f"Section index was wiped on mtime-only bump: got {sections_after}"
        )
        anchors_before = {s["anchor"] for s in sections_before}
        anchors_after = {s["anchor"] for s in sections_after}
        assert anchors_before == anchors_after


# ---------------------------------------------------------------------------
# FIX 3 — duplicate explicit anchors
# ---------------------------------------------------------------------------


class TestFix3DuplicateExplicitAnchors:
    """FIX 3: duplicate explicit anchors must be made unique, not cause UNIQUE errors."""

    def test_duplicate_explicit_anchors_get_suffix(self):
        """Two sections with the same explicit anchor produce 'dup' and 'dup-2'."""
        from pathly_orchestrator.runner.sections import parse_sections

        text = (
            '<!-- pathly:anchor id="dup" -->\n'
            "## First Section\nbody1\n"
            '<!-- pathly:anchor id="dup" -->\n'
            "## Second Section\nbody2\n"
        )
        sections = parse_sections(text)
        assert len(sections) == 2
        anchors = [s.anchor for s in sections]
        assert anchors[0] == "dup"
        assert anchors[1] == "dup-2", f"Expected 'dup-2', got {anchors[1]!r}"

    def test_duplicate_explicit_anchors_reindex_no_unique_error(self, plan_dir):
        """reindex_artifact_sections succeeds when two explicit anchors collide."""
        import uuid
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import (
            reindex_artifact_sections,
            find_or_create_artifact_by_path,
        )
        from pathly_orchestrator.runner.sections import parse_sections

        base, scope, plan_root = plan_dir
        text = (
            '<!-- pathly:anchor id="dup" -->\n'
            "## First Section\nbody1\n"
            '<!-- pathly:anchor id="dup" -->\n'
            "## Second Section\nbody2\n"
        )
        md_path = plan_root / "DUP_ANCHOR.md"
        md_path.write_text(text, encoding="utf-8")

        db = get_db()
        artifact = find_or_create_artifact_by_path(db, scope, str(md_path))
        assert artifact is not None

        sections = parse_sections(text)
        assert len(sections) == 2
        assert sections[0].anchor != sections[1].anchor, (
            "Duplicate explicit anchors must be made unique by parse_sections"
        )

        section_dicts = [
            {
                "id": str(uuid.uuid4()),
                "anchor": s.anchor,
                "heading": s.heading,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "ordinal": s.ordinal,
            }
            for s in sections
        ]

        # Must not raise sqlite3.IntegrityError
        reindex_artifact_sections(
            db, artifact["id"], section_dicts, 0.0, "fakehash", "fake-struct"
        )
