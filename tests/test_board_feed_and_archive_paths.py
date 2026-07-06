"""Board-feed structural inclusion (goals/tasks never evicted) + archive-artifacts repo-root path.

Two production bugs surfaced by long team runs:
  1. get_messages' newest-`limit` window evicted the (oldest) goal messages once run churn filled it,
     stranding every task under "Ungrouped tasks" / an empty Goals view.
  2. run_transition_actions re-derived project_root by walking storage_path up by the flow template's
     segment count — wrong for multi-segment board-scoped topics — so archive-artifacts nested
     pathly/pipeline-walkthrough/ INSIDE the feature folder.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def test_get_messages_structural_survives_limit():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_messages, post_message

    conn = get_db()
    scope = "structfeed-1"
    gid = post_message(conn, board="feature", scope=scope, from_agent="a", type="goal", text="G")
    post_message(conn, board="feature", scope=scope, from_agent="a", type="task", text="T", goal_id=gid)
    # Bury them under more chat messages than the limit.
    for i in range(60):
        post_message(conn, board="feature", scope=scope, from_agent="a", type="status", text=f"s{i}")

    default = get_messages(conn, board="feature", scope=scope, limit=50)
    structural = get_messages(conn, board="feature", scope=scope, limit=50, include_structural=True)

    # The limited feed is bounded; the structural feed ALWAYS carries the goal + task.
    assert len(default) <= 50
    assert sum(1 for m in structural if m["type"] == "goal") == 1
    assert sum(1 for m in structural if m["type"] == "task") == 1
    # An explicit type filter opts out of structural inclusion (still bounded).
    only_status = get_messages(
        conn, board="feature", scope=scope, type="status", limit=50, include_structural=True
    )
    assert all(m["type"] == "status" for m in only_status)


def test_archive_artifacts_uses_repo_root_not_feature_dir(tmp_path):
    from pathly_orchestrator.fsm.engine_actions import run_transition_actions

    topic = "features/f/goals/g-slug"  # multi-segment board-scoped topic
    storage = tmp_path / "pathly" / "features" / "f" / "goals" / "g-slug"
    (storage / "feedback").mkdir(parents=True)
    (storage / "feedback" / "REVIEW_FAILURES.md").write_text("x", encoding="utf-8")
    flow = {
        "storage_path": "pathly/{topic}/",
        "transition_actions": {"RETRO->DONE": [{"skill": "archive-artifacts"}]},
    }

    run_transition_actions(flow, "RETRO", "DONE", storage, topic, 1, project_root=str(tmp_path))

    correct = tmp_path / "pathly" / "pipeline-walkthrough" / "features" / "f" / "goals" / "g-slug" / "artifacts"
    assert correct.exists()  # written at the repo root
    assert not (storage / "pathly").exists()  # NOT nested inside the feature/goal storage dir


def test_run_transition_actions_fallback_without_project_root(tmp_path):
    """Back-compat: single-segment topics still resolve correctly via the walk-up fallback."""
    from pathly_orchestrator.fsm.engine_actions import run_transition_actions

    storage = tmp_path / "pathly" / "solo-feature"
    (storage / "feedback").mkdir(parents=True)
    (storage / "feedback" / "TEST_FAILURES.md").write_text("y", encoding="utf-8")
    flow = {
        "storage_path": "pathly/{topic}/",
        "transition_actions": {"RETRO->DONE": [{"skill": "archive-artifacts"}]},
    }
    run_transition_actions(flow, "RETRO", "DONE", storage, "solo-feature", 1)  # no project_root
    assert (tmp_path / "pathly" / "pipeline-walkthrough" / "solo-feature" / "artifacts").exists()
