"""Tests for comms-board context-retrieval (Phase 3 rigor gate).

Covers §3.1 slug algorithm, parse_sections / structure_key, /section endpoint
(by-id, by-path, path-traversal guard, whole-file, 404 on missing anchor),
staleness detection (§3.4), Board Catalog list_artifacts_catalog, and the §7
backward-compat matrix for retrieve_board_context.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_embed_async(monkeypatch):
    """Stub embed_async and index_artifact_async so tests are synchronous."""
    try:
        import pathly_orchestrator.runner.embeddings as _emb_mod

        monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)
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
    """Create a pathly/plans/<scope>/ directory and return (base, scope)."""
    scope = "test-feature"
    plan_root = tmp_path / "pathly" / "plans" / scope
    plan_root.mkdir(parents=True)
    return tmp_path, scope, plan_root


# ---------------------------------------------------------------------------
# §3.1 slug algorithm — pure, no DB
# ---------------------------------------------------------------------------


def test_slug_phase_n_suffix():
    from pathly_orchestrator.runner.sections import slugify_heading

    assert slugify_heading("Phase 3 — Fix path prefixes") == "phase-3"


def test_slug_phase_n_bare():
    from pathly_orchestrator.runner.sections import slugify_heading

    assert slugify_heading("Phase 3") == "phase-3"


def test_slug_generic():
    from pathly_orchestrator.runner.sections import slugify_heading

    assert slugify_heading("Data layer") == "data-layer"


def test_slug_phase_n_in_edge_cases():
    from pathly_orchestrator.runner.sections import slugify_heading

    assert slugify_heading("Edge Cases: Phase 1") == "phase-1"


def test_slug_explicit_anchor():
    from pathly_orchestrator.runner.sections import slugify_heading

    heading = '<!-- pathly:anchor id="x" --> My heading'
    assert slugify_heading(heading) == "x"


# ---------------------------------------------------------------------------
# parse_sections — correct 1-based inclusive line ranges
# ---------------------------------------------------------------------------


def test_parse_sections_basic_ranges():
    from pathly_orchestrator.runner.sections import parse_sections

    text = "## Phase 1\nline2\nline3\n## Phase 2\nline5\n"
    sections = parse_sections(text)
    assert len(sections) == 2
    s1 = sections[0]
    s2 = sections[1]
    assert s1.anchor == "phase-1"
    assert s1.line_start == 1
    # phase-1 ends the line before phase-2's heading (line 4)
    assert s1.line_end == 3
    assert s2.anchor == "phase-2"
    assert s2.line_start == 4


def test_parse_sections_empty():
    from pathly_orchestrator.runner.sections import parse_sections

    assert parse_sections("") == []
    assert parse_sections(None) == []  # type: ignore[arg-type]


def test_parse_sections_no_headings():
    from pathly_orchestrator.runner.sections import parse_sections

    assert parse_sections("just some text\nno headings here\n") == []


def test_parse_sections_collision_suffix():
    from pathly_orchestrator.runner.sections import parse_sections

    text = "## Phase 1\ncontent a\n## Phase 1\ncontent b\n"
    sections = parse_sections(text)
    assert len(sections) == 2
    assert sections[0].anchor == "phase-1"
    assert sections[1].anchor == "phase-1-2"


def test_parse_sections_explicit_anchor():
    from pathly_orchestrator.runner.sections import parse_sections

    text = '<!-- pathly:anchor id="my-anchor" -->\n## My Heading\ncontent\n'
    sections = parse_sections(text)
    assert len(sections) == 1
    assert sections[0].anchor == "my-anchor"


# ---------------------------------------------------------------------------
# structure_key — order-independent
# ---------------------------------------------------------------------------


def test_structure_key_same_headings_any_order():
    from pathly_orchestrator.runner.sections import parse_sections, structure_key

    text_a = "## Phase 1\nbody\n## Phase 2\nbody\n"
    text_b = "## Phase 2\nbody\n## Phase 1\nbody\n"
    sk_a = structure_key(parse_sections(text_a))
    sk_b = structure_key(parse_sections(text_b))
    assert sk_a == sk_b


def test_structure_key_body_edit_no_change():
    from pathly_orchestrator.runner.sections import parse_sections, structure_key

    text_before = "## Phase 1\noriginal body\n"
    text_after = "## Phase 1\ncompletely different body\n"
    assert structure_key(parse_sections(text_before)) == structure_key(
        parse_sections(text_after)
    )


def test_structure_key_heading_rename_changes():
    from pathly_orchestrator.runner.sections import parse_sections, structure_key

    text_before = "## Phase 1\nbody\n"
    text_after = "## Phase 2\nbody\n"
    assert structure_key(parse_sections(text_before)) != structure_key(
        parse_sections(text_after)
    )


def test_structure_key_add_heading_changes():
    from pathly_orchestrator.runner.sections import parse_sections, structure_key

    text_before = "## Phase 1\nbody\n"
    text_after = "## Phase 1\nbody\n## Phase 2\nmore\n"
    assert structure_key(parse_sections(text_before)) != structure_key(
        parse_sections(text_after)
    )


# ---------------------------------------------------------------------------
# /section endpoint — by-id and by-path
# ---------------------------------------------------------------------------


def _write_plan_file(plan_root: pathlib.Path, filename: str, content: str) -> str:
    """Write a file and return its absolute path string."""
    p = plan_root / filename
    p.write_text(content, encoding="utf-8")
    return str(p)


def _post_artifact(client, scope: str, path: str, feature: str | None = None) -> str:
    """Post an artifact message and return its message_id."""
    feature = feature or scope
    r = client.post(
        "/comms/post",
        json={
            "feature": feature,
            "from": "planner",
            "type": "artifact",
            "text": f"Posted artifact: {os.path.basename(path)}",
            "board": "feature",
            "scope": scope,
            "artifact_path": path,
            "artifact_type": "md",
        },
    )
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def test_section_by_path_returns_full_text(client, plan_dir):
    """By-path /section returns the correct full section text (§4.2)."""
    base, scope, plan_root = plan_dir

    content = "## Phase 1\nline2\nline3\n## Phase 2\nline5\n"
    _write_plan_file(plan_root, "EDGE_CASES.md", content)

    r = client.get(
        "/comms/artifacts/section",
        query_string={
            "scope": scope,
            "artifact": "EDGE_CASES.md",
            "anchor": "phase-1",
            "project_root": str(base),
        },
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert "## Phase 1" in body["text"]
    assert "line2" in body["text"]
    assert "## Phase 2" not in body["text"]


def test_section_by_id_returns_full_text(client, conn, plan_dir, monkeypatch):
    """By-id /section returns the correct section text (§4.1)."""
    base, scope, plan_root = plan_dir

    content = "## Phase 1\nbody1\n## Phase 2\nbody2\n"
    path = _write_plan_file(plan_root, "EDGE_CASES.md", content)

    msg_id = _post_artifact(client, scope, path)

    # get artifact id from the artifacts endpoint — returns {ok, artifacts:[...]}
    r = client.get(f"/comms/artifacts?message_id={msg_id}")
    assert r.status_code == 200, r.data
    data = json.loads(r.data)
    artifacts = data["artifacts"]
    assert artifacts, "expected at least one artifact row"
    artifact_id = artifacts[0]["id"]

    r = client.get(f"/comms/artifacts/{artifact_id}/section?anchor=phase-2")
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["anchor"] == "phase-2"
    assert "body2" in body["text"]


def test_section_missing_anchor_returns_404(client, plan_dir):
    """Requesting a non-existent anchor returns 404 with 'available' list (§4.3)."""
    base, scope, plan_root = plan_dir

    content = "## Phase 1\nbody\n"
    _write_plan_file(plan_root, "EDGE_CASES.md", content)

    r = client.get(
        "/comms/artifacts/section",
        query_string={
            "scope": scope,
            "artifact": "EDGE_CASES.md",
            "anchor": "phase-9",
            "project_root": str(base),
        },
    )
    assert r.status_code == 404, r.data
    body = json.loads(r.data)
    assert body["error"] == "anchor_not_found"
    assert "available" in body
    assert "phase-1" in body["available"]


def test_section_whole_file_when_anchor_omitted(client, plan_dir):
    """Omitting anchor returns the whole file (§4.1 whole-file request)."""
    base, scope, plan_root = plan_dir

    content = "## Phase 1\nbody1\n## Phase 2\nbody2\n"
    _write_plan_file(plan_root, "EDGE_CASES.md", content)

    r = client.get(
        "/comms/artifacts/section",
        query_string={
            "scope": scope,
            "artifact": "EDGE_CASES.md",
            "project_root": str(base),
        },
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["anchor"] is None
    assert "Phase 1" in body["text"]
    assert "Phase 2" in body["text"]


# ---------------------------------------------------------------------------
# Path-traversal guard (§4.3) — SECURITY CRITICAL
# ---------------------------------------------------------------------------


def test_path_traversal_dotdot_rejected(client, plan_dir):
    """../escape is rejected with 400 path_out_of_scope."""
    _, scope, _ = plan_dir
    r = client.get(
        "/comms/artifacts/section",
        query_string={"scope": scope, "artifact": "../../../etc/passwd", "anchor": "x"},
    )
    assert r.status_code == 400, r.data
    body = json.loads(r.data)
    assert body["error"] == "path_out_of_scope"


def test_path_traversal_separator_in_artifact_rejected(client, plan_dir):
    """A slash in artifact basename (separator) is rejected with 400."""
    _, scope, _ = plan_dir
    r = client.get(
        "/comms/artifacts/section",
        query_string={"scope": scope, "artifact": "subdir/file.md", "anchor": "x"},
    )
    assert r.status_code == 400, r.data
    body = json.loads(r.data)
    assert body["error"] == "path_out_of_scope"


def test_path_traversal_backslash_in_artifact_rejected(client, plan_dir):
    """A backslash in artifact basename is rejected with 400."""
    _, scope, _ = plan_dir
    r = client.get(
        "/comms/artifacts/section",
        query_string={"scope": scope, "artifact": "subdir\\file.md", "anchor": "x"},
    )
    assert r.status_code == 400, r.data
    body = json.loads(r.data)
    assert body["error"] == "path_out_of_scope"


def test_section_by_path_uses_cwd_when_no_project_root(client, plan_dir, monkeypatch):
    """drain-dag (single executor) sends only scope+artifact+anchor (spec §4.1) — no
    project_root. The route must fall back to the server CWD so hydration still works.
    """
    base, scope, plan_root = plan_dir
    _write_plan_file(
        plan_root, "EDGE_CASES.md", "## Phase 1 — setup\nedge body for phase 1\n"
    )
    monkeypatch.chdir(base)  # server CWD = project root (where pathly/plans/ lives)
    r = client.get(
        "/comms/artifacts/section",
        query_string={"scope": scope, "artifact": "EDGE_CASES.md", "anchor": "phase-1"},
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert "edge body for phase 1" in body["text"]


# ---------------------------------------------------------------------------
# Staleness detection (§3.4)
# ---------------------------------------------------------------------------


def test_staleness_body_edit_no_structure_key_change(tmp_path):
    """Editing only body text re-parses line-ranges but does NOT change structure_key."""
    from pathly_orchestrator.runner.sections import parse_sections, structure_key

    text_before = "## Phase 1\noriginal body text\n"
    text_after = "## Phase 1\nedited body text with more content\n"

    sk_before = structure_key(parse_sections(text_before))
    sk_after = structure_key(parse_sections(text_after))
    assert sk_before == sk_after, "structure_key must not change on body-only edit"


def test_never_indexed_artifact_builds_index_on_first_hydrate(plan_dir):
    """A never-indexed artifact builds its section index on first hydrate call."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.hydrate import hydrate_section

    base, scope, plan_root = plan_dir
    content = "## Phase 1\nbody content\n"
    _write_plan_file(plan_root, "TEST.md", content)

    conn = get_db()
    result = hydrate_section(
        conn, scope=scope, artifact="TEST.md", anchor="phase-1", project_root=str(base)
    )
    assert result["status"] == 200, result
    assert "body content" in result["body"]["text"]
    # stale_rebuilt should be True because it was a first-time build
    assert result["body"]["stale_rebuilt"] is True


def test_cached_index_returned_on_unchanged_file(plan_dir):
    """Second hydrate of unchanged file should be served from cache (stale_rebuilt=False)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.hydrate import hydrate_section

    base, scope, plan_root = plan_dir
    content = "## Phase 1\nbody\n"
    _write_plan_file(plan_root, "CACHED.md", content)

    conn = get_db()
    # First call — builds index
    result1 = hydrate_section(
        conn,
        scope=scope,
        artifact="CACHED.md",
        anchor="phase-1",
        project_root=str(base),
    )
    assert result1["status"] == 200

    # Second call — should use cache
    result2 = hydrate_section(
        conn,
        scope=scope,
        artifact="CACHED.md",
        anchor="phase-1",
        project_root=str(base),
    )
    assert result2["status"] == 200
    assert result2["body"]["stale_rebuilt"] is False


# ---------------------------------------------------------------------------
# Board Catalog — list_artifacts_catalog (§5a.4)
# ---------------------------------------------------------------------------


def test_catalog_scoped_to_board(client, conn, plan_dir):
    """list_artifacts_catalog is board/scope-scoped (§5a.4)."""
    from pathly_orchestrator.db.queries.comms import list_artifacts_catalog

    _, scope, plan_root = plan_dir
    path = _write_plan_file(plan_root, "DOC.md", "## Heading\ntext\n")

    # Post artifact message on the feature board via HTTP (triggers insert_artifact)
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "planner",
            "type": "artifact",
            "text": "Posted DOC",
            "board": "feature",
            "scope": scope,
            "artifact_path": path,
            "artifact_type": "md",
        },
    )
    assert r.status_code == 200, r.data

    rows = list_artifacts_catalog(conn, scope, exposed_boards=["feature"])
    assert isinstance(rows, list)
    paths = [r["path"] for r in rows]
    assert path in paths, "posted artifact must appear in catalog"


def test_catalog_null_summary_row_still_returned(conn, plan_dir):
    """A NULL summary row still appears in the catalog (§7, §5a.4)."""
    from pathly_orchestrator.db.queries.comms import (
        list_artifacts_catalog,
        post_message,
    )
    from pathly_orchestrator.db.connection import _get_write_lock

    _, scope, plan_root = plan_dir
    path = _write_plan_file(plan_root, "NO_SUMMARY.md", "## Heading\n")

    # Create sentinel row with NULL summary via the DB directly
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    msg_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_messages (id, board, scope, from_agent, to_agent, type, text, ts) "
            "VALUES (?, 'feature', ?, 'system', '*', 'artifact', 'artifact post', ?)",
            (msg_id, scope, now),
        )
        conn.execute(
            "INSERT INTO comms_artifacts (id, message_id, path, type, title, created_at, created_by, version) "
            "VALUES (?, ?, ?, 'md', 'NO_SUMMARY', ?, 'system', 1)",
            (artifact_id, msg_id, path, now),
        )
        conn.commit()

    rows = list_artifacts_catalog(conn, scope, exposed_boards=["feature"])
    found = [r for r in rows if r["path"] == path]
    assert found, "artifact with NULL summary must appear in catalog"
    assert found[0]["summary"] is None  # consumer falls back to path/title per §7


def test_catalog_find_or_create_for_legacy_plan_file(conn, plan_dir):
    """find_or_create_artifact_by_path resolves a legacy plan file with no DB row (§7)."""
    from pathly_orchestrator.db.queries.comms import find_or_create_artifact_by_path

    _, scope, plan_root = plan_dir
    path = _write_plan_file(plan_root, "LEGACY.md", "## Old heading\nlegacy content\n")

    # No artifact row exists — should create a sentinel
    result = find_or_create_artifact_by_path(conn, scope, path)
    assert result is not None
    assert result["path"] == path
    assert result["id"]  # non-empty ID

    # Calling again returns the same row (idempotent)
    result2 = find_or_create_artifact_by_path(conn, scope, path)
    assert result2["id"] == result["id"]


def test_catalog_missing_path_returns_none(conn, plan_dir):
    """find_or_create_artifact_by_path returns None for a non-existent file."""
    from pathly_orchestrator.db.queries.comms import find_or_create_artifact_by_path

    _, scope, plan_root = plan_dir
    result = find_or_create_artifact_by_path(
        conn, scope, str(plan_root / "NONEXISTENT.md")
    )
    assert result is None


# ---------------------------------------------------------------------------
# §7 Backward-compat matrix — retrieve_board_context
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_embed(monkeypatch):
    """Force embed() to return None (recency fallback) for all context tests."""
    try:
        import pathly_orchestrator.runner.embeddings as _emb_mod

        monkeypatch.setattr(_emb_mod, "embed", lambda text: None)
    except Exception:
        pass


def test_backward_compat_no_task_id_no_pinned_marker():
    """§7(b): retrieve_board_context called without task_id → Referenced marker is absent."""
    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="compat-feature",
        project_root="C:/proj",
        task_description="do something",
        board_scope={"feature": True, "project": False, "global": False},
        task_id=None,
    )
    # No Referenced channel when task_id=None
    assert "### Referenced context" not in block


def test_backward_compat_task_id_set_but_no_context_refs(client):
    """§7(c): task with NO context_refs + task_id → no Referenced channel emitted."""
    import json

    # Post a task with no context_refs
    r = client.post(
        "/comms/post",
        json={
            "feature": "compat2",
            "from": "planner",
            "type": "task",
            "text": "legacy task with no refs",
            "board": "feature",
            "scope": "compat2",
        },
    )
    assert r.status_code == 200, r.data
    task_id = json.loads(r.data)["message_id"]

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="compat2",
        project_root="C:/proj",
        task_description="legacy task with no refs",
        board_scope={"feature": True, "project": False, "global": False},
        task_id=task_id,
    )
    assert (
        "### Referenced context" not in block
    ), "no referenced channel when context_refs is NULL"


def test_backward_compat_task_id_none_identical_to_before(client):
    """§7(a): task_id=None produces output byte-identical (Referenced absent) on same board."""
    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    # Post a decision so the board is non-empty (triggers Governance)
    r = client.post(
        "/comms/post",
        json={
            "feature": "compat3",
            "from": "human",
            "type": "decision",
            "text": "Use SQLite",
            "board": "feature",
            "scope": "compat3",
        },
    )
    assert r.status_code == 200, r.data

    block_no_task_id = retrieve_board_context(
        topic="compat3",
        project_root="C:/proj",
        task_description="build the feature",
        board_scope={"feature": True, "project": False, "global": False},
        task_id=None,
    )
    # Regardless of task_id=None: no Referenced channel
    assert "### Referenced context" not in block_no_task_id
    # The governance decision should still appear
    assert "Use SQLite" in block_no_task_id


def test_context_refs_emits_pinned_channel(client, conn, plan_dir):
    """§5.1 positive path: a task WITH a resolvable context_refs emits the Referenced
    context channel containing the hydrated FULL section text. This is the path the loop
    executor now exercises — scheduler threads task_id → board_context_for →
    retrieve_board_context (regression for the dropped-task_id wiring bug)."""
    import json

    base, scope, plan_root = plan_dir
    _write_plan_file(
        plan_root,
        "EDGE_CASES.md",
        "## Phase 1 — first phase\nedge case body for phase one\n\n## Phase 2\nother\n",
    )

    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "planner",
            "type": "task",
            "text": "Phase 1: do the thing",
            "board": "feature",
            "scope": scope,
            "context_refs": [{"artifact": "EDGE_CASES.md", "anchor": "phase-1"}],
        },
    )
    assert r.status_code == 200, r.data
    task_id = json.loads(r.data)["message_id"]

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic=scope,
        project_root=str(base),
        task_description="Phase 1: do the thing",
        board_scope={"feature": True, "project": False, "global": False},
        task_id=task_id,
    )
    assert "### Referenced context" in block, block
    assert "EDGE_CASES.md" in block
    # the lossless HYDRATE payload — the full section body, not a summary
    assert "edge case body for phase one" in block
