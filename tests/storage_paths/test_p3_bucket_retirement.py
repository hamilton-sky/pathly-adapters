"""board-scoped-storage P3: shared buckets retired from discovery; nested kinds resolve.

After P2 moved every bucket run under its board, the top-level pathly/debugs and
pathly/explorations roots are no longer scanned (a stray reappearance is invisible to
the CLI by design — the reserved-name set still blocks them as feature names). Reads
and writes must land in the same place for every tier: what board_run_topic +
_resolve_storage_path write, iter_state_files / find_topic_dir find.
"""

from __future__ import annotations

import json
from pathlib import Path

from pathly_orchestrator.cli._discovery import find_topic_dir, iter_state_files
from pathly_orchestrator.fsm_ops import _resolve_storage_path
from pathly_orchestrator.supervisor.goal_decomposer import board_run_topic


def _mk_state(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "STATE.json").write_text(
        json.dumps({"current": "PLANNING", "updated_at": "2026-07-22"}),
        encoding="utf-8",
    )


def test_buckets_retired_but_nested_kinds_discovered(tmp_path: Path) -> None:
    # stray legacy bucket runs — NOT discovered anymore (P3 retirement)
    _mk_state(tmp_path / "pathly" / "debugs" / "old-bucket-debug")
    _mk_state(tmp_path / "pathly" / "explorations" / "old-bucket-explore")
    # board-scoped nested runs — discovered
    _mk_state(tmp_path / "pathly" / "features" / "feat-a" / "debugs" / "d1")
    _mk_state(tmp_path / "pathly" / "project" / "explorations" / "e1")
    # plain feature + legacy plans — still discovered (unchanged back-compat)
    _mk_state(tmp_path / "pathly" / "features" / "feat-a")
    _mk_state(tmp_path / "pathly" / "plans" / "legacy-feat")

    topics = {t for _, _, t in iter_state_files(tmp_path)}
    assert {"d1", "e1", "feat-a", "legacy-feat"} <= topics
    assert "old-bucket-debug" not in topics
    assert "old-bucket-explore" not in topics


def test_reads_and_writes_land_in_the_same_place_feature_tier(tmp_path: Path) -> None:
    """A feature-board debug run: the executor materializes the board-scoped dir
    before resolving (goal_executor does os.makedirs on the topic path), then the
    resolver lands there, and find_topic_dir finds that dir back by slug."""
    topic = board_run_topic("feature", "feat-a", "debugs", "slug-x")
    target = tmp_path / "pathly" / Path(*topic.split("/"))
    _mk_state(target)  # materialized at launch, exactly like the executor
    storage = _resolve_storage_path(None, str(tmp_path), topic)
    assert storage == target
    assert target == tmp_path / "pathly" / "features" / "feat-a" / "debugs" / "slug-x"

    found = find_topic_dir(tmp_path, "slug-x")
    assert found is not None
    assert found[0] == storage
    assert found[1] == "debug"


def test_reads_and_writes_land_in_the_same_place_project_tier(tmp_path: Path) -> None:
    topic = board_run_topic("project", str(tmp_path), "explorations", "slug-y")
    target = tmp_path / "pathly" / Path(*topic.split("/"))
    _mk_state(target)
    storage = _resolve_storage_path(None, str(tmp_path), topic)
    assert storage == target
    assert target == tmp_path / "pathly" / "project" / "explorations" / "slug-y"

    found = find_topic_dir(tmp_path, "slug-y")
    assert found is not None
    assert found[0] == storage
    assert found[1] == "explore"


def test_reserved_names_still_blocked_as_feature_names(tmp_path: Path) -> None:
    """The retired bucket names stay in the reserved set — a top-level
    pathly/<bucket>/STATE.json is never mistaken for a flat feature."""
    _mk_state(tmp_path / "pathly" / "fixes")
    _mk_state(tmp_path / "pathly" / "debugs")
    topics = {t for _, _, t in iter_state_files(tmp_path)}
    assert "fixes" not in topics
    assert "debugs" not in topics
