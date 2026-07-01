"""Dual-root feature discovery for the pathly-* CLI shortcuts (storage-path-alignment)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from pathly_orchestrator.cli._discovery import (
    find_most_recent_state,
    find_topic_dir,
    iter_state_files,
)


def _mk(root: Path, rel: str, state: str = "BUILDING") -> Path:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "STATE.json").write_text(json.dumps({"current": state}), encoding="utf-8")
    return d


def test_iter_finds_legacy_and_new_root(tmp_path):
    _mk(tmp_path, "pathly/plans/legacy-feat")     # legacy nested root
    _mk(tmp_path, "pathly/new-feat")              # new top-level root
    _mk(tmp_path, "pathly/.archive/old-feat")     # archived → excluded
    _mk(tmp_path, "pathly/goals/some-goal")       # reserved container child → excluded
    found = {sf.parent.name for sf, _flow in iter_state_files(tmp_path)}
    assert found == {"legacy-feat", "new-feat"}


def test_find_topic_prefers_new_root(tmp_path):
    _mk(tmp_path, "pathly/myfeat")
    res = find_topic_dir(tmp_path, "myfeat")
    assert res == (tmp_path / "pathly" / "myfeat", "team")


def test_find_topic_falls_back_to_legacy(tmp_path):
    _mk(tmp_path, "pathly/plans/legacyfeat")
    res = find_topic_dir(tmp_path, "legacyfeat")
    assert res == (tmp_path / "pathly" / "plans" / "legacyfeat", "team")


def test_most_recent_across_roots(tmp_path):
    _mk(tmp_path, "pathly/plans/older")
    b = _mk(tmp_path, "pathly/newer")
    later = time.time() + 10
    os.utime(b / "STATE.json", (later, later))
    res = find_most_recent_state(tmp_path)
    assert res is not None
    _storage, topic, _flow = res
    assert topic == "newer"
