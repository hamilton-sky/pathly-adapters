"""prompt_library query layer — CRUD, name-upsert, and global/project merge.

The autouse conftest fixture points get_db() at a per-test temp DB with migrations
applied, so each test starts from an empty prompt_library table.
"""

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.prompt_library import (
    create_prompt,
    delete_prompt,
    get_prompt,
    list_prompts,
    seed_builtins,
    update_prompt,
)


def test_create_and_list():
    conn = get_db()
    row = create_prompt(
        conn,
        kind="preset",
        category="analyze",
        name="mylens",
        label="My lens",
        body="Do a thing.",
    )
    assert row["id"].startswith("pl_")
    assert row["source"] == "user"
    got = list_prompts(conn, kind="preset", category="analyze")
    assert any(p["name"] == "mylens" for p in got)


def test_create_is_upsert_on_name_within_scope():
    """Re-adding the same name edits in place (name is the natural key within a scope)."""
    conn = get_db()
    create_prompt(
        conn, kind="preset", category="eval", name="dup", label="A", body="one"
    )
    create_prompt(
        conn, kind="preset", category="eval", name="dup", label="B", body="two"
    )
    rows = [
        p
        for p in list_prompts(conn, kind="preset", category="eval")
        if p["name"] == "dup"
    ]
    assert len(rows) == 1
    assert rows[0]["label"] == "B" and rows[0]["body"] == "two"


def test_project_row_overrides_global():
    conn = get_db()
    create_prompt(
        conn, kind="ability", category="build", name="tdd", label="Global TDD", body="g"
    )
    create_prompt(
        conn,
        kind="ability",
        category="build",
        name="tdd",
        label="Proj TDD",
        body="p",
        project_root="C:/proj",
    )
    proj = [
        p
        for p in list_prompts(conn, project_root="C:/proj", kind="ability")
        if p["name"] == "tdd"
    ]
    assert len(proj) == 1 and proj[0]["label"] == "Proj TDD"
    # a run with no project sees only the global row
    glob = [p for p in list_prompts(conn, kind="ability") if p["name"] == "tdd"]
    assert len(glob) == 1 and glob[0]["label"] == "Global TDD"


def test_norm_root_matches_backslash_and_forward_slash():
    """A Windows write (backslashes) and a forward-slash read hit the same scope key."""
    conn = get_db()
    create_prompt(
        conn,
        kind="ability",
        category="plan",
        name="x",
        label="X",
        body="b",
        project_root="C:\\Users\\me\\proj",
    )
    got = [
        p
        for p in list_prompts(conn, project_root="C:/Users/me/proj", kind="ability")
        if p["name"] == "x"
    ]
    assert len(got) == 1


def test_update_and_delete():
    conn = get_db()
    row = create_prompt(
        conn, kind="preset", category="diagram", name="z", label="Z", body="b"
    )
    upd = update_prompt(conn, row["id"], {"label": "Z2", "body": "b2"})
    assert upd is not None and upd["label"] == "Z2" and upd["body"] == "b2"
    # untouched fields survive
    assert upd["category"] == "diagram" and upd["name"] == "z"
    assert delete_prompt(conn, row["id"]) is True
    assert get_prompt(conn, row["id"]) is None


def test_update_unknown_id_returns_none():
    assert update_prompt(get_db(), "pl_nope", {"label": "x"}) is None


def test_ability_segments_from_library():
    """editor_render._ability_segments turns kind='ability' rows into ability segments,
    skipping unknown / non-ability ids (fail-soft)."""
    from pathly_orchestrator.http_server.blueprints.skills.editor_render import (
        _ability_segments,
    )

    conn = get_db()
    row = create_prompt(
        conn,
        kind="ability",
        category="build",
        name="react-web",
        label="React web",
        body="## React web\nPrefer function components.",
    )
    segs = _ability_segments([row["id"]], "")
    assert len(segs) == 1
    assert segs[0]["kind"] == "ability" and segs[0]["source"] == "ability"
    assert segs[0]["optional"] is True
    assert "Prefer function components." in segs[0]["text"]

    # a preset id (non-ability) and an unknown id are both skipped
    preset = create_prompt(
        conn, kind="preset", category="system", name="p", label="P", body="x"
    )
    assert _ability_segments([preset["id"], "pl_nope"], "") == []


def test_seed_builtins_idempotent_and_preserves_user_edit():
    conn = get_db()
    rows = [
        {
            "kind": "preset",
            "category": "system",
            "name": "Summarizer",
            "label": "Summarizer",
            "body": "Be terse.",
        }
    ]
    assert seed_builtins(conn, rows) == 1
    assert seed_builtins(conn, rows) == 0  # idempotent — no duplicate

    got = [
        p
        for p in list_prompts(conn, kind="preset", category="system")
        if p["name"] == "Summarizer"
    ]
    assert len(got) == 1 and got[0]["source"] == "builtin"

    # a user edit to a seeded prompt must survive the next seed pass
    update_prompt(conn, got[0]["id"], {"body": "Edited."})
    assert seed_builtins(conn, rows) == 0
    again = [
        p
        for p in list_prompts(conn, kind="preset", category="system")
        if p["name"] == "Summarizer"
    ]
    assert again[0]["body"] == "Edited."
