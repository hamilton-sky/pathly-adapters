"""Binding decisions (standing orders) keep reaching the prompts of the roles they target.

Today a decision reaches a prompt only while it is `pending`, and `/comms/acknowledge` sets the
row `active`, so the next prompt no longer carries it. A binding decision (`binding = 1`) is
read for every prompt, whatever its status, until it is superseded or deleted:

- addressed to the prompt's role or to `*` (an empty role takes `*` only);
- from the tiers the run reads, and ALWAYS from the project board, even when the project tier
  is off for the role (a standing order is not muted by a context-budget toggle);
- rendered in a standing-orders block of its own, outside the ranked decision list, so a newer
  ordinary decision cannot outrank it.

Rows are inserted through `post_message` and `binding` is set directly: `POST /comms/directives`
(the only door that sets it) is a later ticket.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from binding_support import (
    ALL,
    FLOW,
    NO_DEPS,
    NO_PROJECT,
    NONE,
    ONLY_BUILDER,
    RANKED,
    ROOT,
    STANDING,
    TOPIC,
    directive,
    governance_part,
    post,
    ranked_part,
    render,
    retire,
    standing_part,
)


@pytest.fixture(autouse=True)
def _recency_path(monkeypatch):
    """No embedding model: the semantic channel falls back to recency, which is the
    channel an ordinary acknowledged decision still shows up in."""
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(emb, "embed_async", lambda *a, **k: None)
    monkeypatch.setattr(emb, "embed", lambda *a, **k: None)


# --- who gets which directive -------------------------------------------------


@pytest.mark.parametrize("role", ["builder", "reviewer", "tester"])
def test_acknowledged_star_directive_reaches_every_role(role):
    mid = directive(NO_DEPS)
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT status FROM comms_messages WHERE id=?", (mid,))
        .fetchone()
    )
    assert row["status"] == "active", "acknowledged: the pending query no longer has it"
    counts: dict = {}
    assert NO_DEPS in governance_part(render(role, counts=counts))
    assert counts["governance"] == 1


@pytest.mark.parametrize("acked", [False, True])
def test_directive_for_builder_reaches_the_builder_only(acked):
    directive(ONLY_BUILDER, to_agent="builder", acked=acked)
    assert ONLY_BUILDER in governance_part(render("builder"))
    for other in ("reviewer", "tester", ""):
        assert ONLY_BUILDER not in render(other), f"leaked to role {other!r}"


@pytest.mark.parametrize("column", ["superseded_by", "deleted_at"])
@pytest.mark.parametrize("role", ["builder", "reviewer", ""])
def test_superseded_or_deleted_directive_reaches_nobody(column, role):
    retire(directive(NO_DEPS), column)
    assert NO_DEPS not in render(role)


def test_acknowledged_non_binding_decision_is_not_governance():
    """As today: acknowledging an ordinary decision drops it from the governance block."""
    post("Prefer tabs.")
    counts: dict = {}
    block = render("builder", counts=counts)
    assert counts["governance"] == 0
    assert "Prefer tabs." not in governance_part(block)


def test_pending_non_binding_decision_is_still_governance_for_every_role():
    post("Prefer tabs.", acked=False)
    for role in ("builder", "reviewer", ""):
        assert "Prefer tabs." in governance_part(render(role))


def test_pending_directive_shows_once_and_as_a_standing_order():
    directive(NO_DEPS, acked=False)
    gov = governance_part(render("builder"))
    assert gov.count(NO_DEPS) == 1
    assert NO_DEPS in standing_part(gov)
    assert NO_DEPS not in ranked_part(gov)


def test_directive_on_another_project_does_not_appear():
    directive(NO_DEPS, scope="C:/other")
    assert NO_DEPS not in render("builder")


# --- project board is always read ---------------------------------------------


def test_project_directive_survives_the_project_tier_being_off():
    directive(NO_DEPS)
    assert NO_DEPS in governance_part(render("builder", board_scope=NO_PROJECT))


def test_feature_directive_follows_its_own_tier_toggle():
    """Only the project board is always read; a feature-board directive obeys its toggle."""
    directive(NO_DEPS, board="feature", scope=TOPIC)
    assert NO_DEPS in governance_part(render("builder"))
    assert NO_DEPS not in render("builder", board_scope={**ALL, "feature": False})


def test_project_directive_survives_every_tier_being_off():
    directive(NO_DEPS)
    block = render("builder", board_scope=NONE)
    assert block.startswith("## Communication Board")
    assert NO_DEPS in standing_part(governance_part(block))


def test_every_tier_off_without_a_directive_is_still_empty():
    post("Prefer tabs.", acked=False)
    assert render("builder", board_scope=NONE) == ""


# --- the query and the merge --------------------------------------------------


def test_get_binding_decisions_rules():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_directives import get_binding_decisions

    first = directive("first", to_agent="builder")
    second = directive("second")
    directive("other role", to_agent="reviewer")
    directive("no addressee", to_agent="")
    post("not binding")
    retire(directive("deleted"), "deleted_at")
    retire(directive("superseded"), "superseded_by")
    conn = get_db()
    ids = [r["id"] for r in get_binding_decisions(conn, ["project"], [ROOT], "builder")]
    assert ids == [first, second], "oldest first, this role and * only"
    star_only = get_binding_decisions(conn, ["project"], [ROOT], "")
    assert [r["id"] for r in star_only] == [second]
    assert get_binding_decisions(conn, [], [ROOT], "builder") == []
    assert get_binding_decisions(conn, ["project"], [], "builder") == []


def test_get_binding_decisions_takes_the_lists_as_data():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_directives import get_binding_decisions

    directive(NO_DEPS)
    conn = get_db()
    hostile = ["x') OR 1=1 --", 'a"b', "']"]
    assert get_binding_decisions(conn, hostile, hostile, "builder") == []
    got = get_binding_decisions(conn, ["project"], [*hostile, ROOT], "x' OR '1'='1")
    texts = [r["text"] for r in got]
    assert texts == [NO_DEPS], "quotes in a list or the role are data"


def test_governance_decisions_marks_and_dedupes():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.comms_governance import governance_decisions

    mid = directive(NO_DEPS)
    pending = post("Prefer tabs.", acked=False)
    rows = governance_decisions(
        get_db(), ["feature", "project"], [TOPIC, ROOT], "builder", ROOT
    )
    by_id = {r["id"]: r for r in rows}
    assert sorted(by_id) == sorted([mid, pending]), "the project row comes once"
    assert by_id[mid]["_binding"] is True
    assert not by_id[pending].get("_binding")


def test_a_stored_binding_flag_alone_does_not_make_a_standing_order():
    """The formatter trusts the mark the merge sets, not a `binding` value on a row."""
    from pathly_orchestrator.runner.comms_formatters import render_governance_lines

    row = {"id": "d1", "text": "X", "ts": "2026-08-10T15:05:00", "board": "project"}
    plain = "\n".join(render_governance_lines([{**row, "binding": 1}], []))
    assert STANDING not in plain
    marked = "\n".join(render_governance_lines([{**row, "_binding": True}], []))
    assert STANDING in marked and RANKED not in marked


# --- rendering ----------------------------------------------------------------


def test_directive_is_a_standing_order_and_a_newer_decision_does_not_displace_it():
    mid = directive(NO_DEPS)
    newer = "Dependencies are fine now; add lodash."
    post(newer, acked=False)
    gov = governance_part(render("builder"))
    assert NO_DEPS in standing_part(gov) and newer not in standing_part(gov)
    assert newer in ranked_part(gov) and NO_DEPS not in ranked_part(gov)
    assert gov.index(NO_DEPS) < gov.index(newer), "standing orders come first"
    latest = next(line for line in gov.splitlines() if "LATEST" in line)
    assert newer in latest, "the ranked list still ranks its own decisions"
    assert f"[id: {mid}]" in standing_part(gov)


def test_standing_order_lines_name_the_role_and_do_not_offer_a_supersede():
    directive(NO_DEPS)
    directive(ONLY_BUILDER, to_agent="builder")
    gov = governance_part(render("builder"))
    standing = standing_part(gov)
    assert f"BINDING for all roles: {NO_DEPS}  [id: " in standing
    assert f"BINDING for builder: {ONLY_BUILDER}  [id: " in standing
    assert "a newer decision does not override them" in gov
    assert "through the chief" in standing
    assert "supersedes" not in standing, "the hint stays with the ranked list"


def test_no_directive_means_no_standing_orders_block():
    post("Prefer tabs.", acked=False)
    assert STANDING not in render("builder")


def test_a_run_with_only_directives_has_no_ranked_list():
    directive(NO_DEPS)
    gov = governance_part(render("builder"))
    assert STANDING in gov and RANKED not in gov


# --- the three prompt paths ---------------------------------------------------


def _storage(tmp_path):
    from pathly_orchestrator.fsm_compose import _project_root_from_storage

    storage = tmp_path / "pathly" / "features" / TOPIC
    storage.mkdir(parents=True)
    return storage, _project_root_from_storage(storage).replace("\\", "/").rstrip("/")


@pytest.mark.parametrize("state", ["BUILDING", "REVIEWING", "TESTING"])
def test_fsm_prompt_carries_an_acknowledged_star_directive(tmp_path, state):
    from pathly_orchestrator.fsm_compose import build_prompt

    storage, root = _storage(tmp_path)
    directive(NO_DEPS, scope=root)
    prompt = build_prompt(FLOW, state, storage)
    assert STANDING in prompt
    assert NO_DEPS in prompt


@pytest.mark.parametrize(
    "state, reaches",
    [("BUILDING", True), ("REVIEWING", False), ("TESTING", False)],
)
def test_fsm_prompt_passes_the_stage_role(tmp_path, state, reaches):
    from pathly_orchestrator.fsm_compose import build_prompt

    storage, root = _storage(tmp_path)
    directive(ONLY_BUILDER, to_agent="builder", scope=root)
    assert (ONLY_BUILDER in build_prompt(FLOW, state, storage)) is reaches


def test_fsm_prompt_with_an_empty_role_carries_star_directives_only(tmp_path):
    from pathly_orchestrator.fsm_compose import build_prompt

    storage, root = _storage(tmp_path)
    directive(NO_DEPS, scope=root)
    directive(ONLY_BUILDER, to_agent="builder", scope=root)
    flow = {"agent_map": {"BUILDING": ""}, "composition": {}}
    prompt = build_prompt(flow, "BUILDING", storage, stage_override="Stage text.")
    assert NO_DEPS in prompt
    assert ONLY_BUILDER not in prompt


@pytest.mark.parametrize(
    "agent, role",
    [
        ("team/build", "builder"),
        ("debug/build", "build"),
        ("fix/build", "build"),
        ("scout", "scout"),
        ("", ""),
    ],
)
def test_role_of_a_stage_is_pinned_so_a_change_to_the_table_is_deliberate(agent, role):
    """`_SKILL_AGENT_ROLE` knows six skills; any other agent takes its last `/` segment, so a
    directive addressed to `builder` misses the debug and quick-fix fixers (`build`) and only
    `*` directives reach them. Safe: nothing reaches the wrong role. Change it on purpose.
    """
    from pathly_orchestrator.fsm_compose_tables import agent_role_of

    assert agent_role_of(agent) == role
    directive(NO_DEPS)
    directive(ONLY_BUILDER, to_agent="builder")
    block = render(agent_role_of(agent))
    assert NO_DEPS in block
    assert (ONLY_BUILDER in block) is (role == "builder")


def test_dag_task_prompt_is_read_as_the_builder(tmp_path):
    from pathly_orchestrator.supervisor.task_prompt import build_task_prompt

    _, root = _storage(tmp_path)
    directive(ONLY_BUILDER, to_agent="builder", scope=root)
    directive("The reviewer reads the diff first.", to_agent="reviewer", scope=root)
    state = SimpleNamespace(project_root=root, topic=TOPIC, goal_id="", storage_path="")
    prompt = build_task_prompt(
        {"id": "t1", "text": "do the thing"},
        state,
        "feature",
        TOPIC,
        adapter="claude",
        task_id="t1",
    )
    assert ONLY_BUILDER in prompt
    assert "The reviewer reads the diff first." not in prompt


def test_board_run_prompt_renders_the_same_standing_orders_block(tmp_path):
    from pathly_orchestrator.supervisor.board_run import start_board_run

    _, root = _storage(tmp_path)
    directive(NO_DEPS, scope=root)
    directive(ONLY_BUILDER, to_agent="builder", scope=root)
    calls: list = []

    def spawn(**kwargs):
        calls.append(kwargs)
        return {"result": "ok"}

    out = start_board_run(
        "feature",
        TOPIC,
        "single-agent",
        "Look at the board",
        project_root=root,
        agent="reviewer",
        spawn_fn=spawn,
        block=True,
    )
    assert out["ok"] is True
    prompt = calls[0]["prompt"]
    assert STANDING in prompt and NO_DEPS in prompt
    assert ONLY_BUILDER not in prompt, "role=agent reaches the query"


# --- the column ---------------------------------------------------------------


def test_migration_adds_binding_and_runs_twice():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.migrations_incremental import _add_additive_migrations

    conn = get_db()

    def column():
        info = conn.execute("PRAGMA table_info(comms_messages)").fetchall()
        return next((tuple(r) for r in info if r[1] == "binding"), None)

    assert column() is not None, "a fresh database has the column"
    # An upgrade: a database from before this change has rows and no column.
    old = post("old row", acked=False)
    conn.execute("ALTER TABLE comms_messages DROP COLUMN binding")
    assert column() is None
    _add_additive_migrations(conn)
    _add_additive_migrations(conn)
    col = column()
    assert col[2] == "INTEGER" and col[3] == 1 and col[4] == "0"
    row = conn.execute("SELECT binding FROM comms_messages WHERE id=?", (old,))
    assert row.fetchone()["binding"] == 0
