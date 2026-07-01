"""Dual-root feature discovery for the pathly-* CLI shortcuts (storage-restructure)."""

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


def test_iter_finds_all_three_layouts(tmp_path):
    _mk(tmp_path, "pathly/features/new-feat/plans")   # feature-centric (topic = grandparent)
    _mk(tmp_path, "pathly/plans/legacy-feat")         # legacy type-nested
    _mk(tmp_path, "pathly/flat-feat")                 # legacy flat
    _mk(tmp_path, "pathly/.archive/old-feat")         # archived → excluded
    _mk(tmp_path, "pathly/goals/some-goal")           # reserved container child → excluded
    found = {topic for _sf, _flow, topic in iter_state_files(tmp_path)}
    assert found == {"new-feat", "legacy-feat", "flat-feat"}


def test_iter_finds_flat_feature_centric(tmp_path):
    # current layout: pathly/features/<name>/STATE.json (no plans/ subfolder)
    _mk(tmp_path, "pathly/features/flat-feat")
    _mk(tmp_path, "pathly/features/.archive/old-feat")  # archived → excluded
    found = {topic for _sf, _flow, topic in iter_state_files(tmp_path)}
    assert found == {"flat-feat"}


def test_find_topic_prefers_flat_feature_root(tmp_path):
    _mk(tmp_path, "pathly/features/myfeat")
    res = find_topic_dir(tmp_path, "myfeat")
    assert res == (tmp_path / "pathly" / "features" / "myfeat", "team")


def test_find_topic_prefers_feature_root(tmp_path):
    _mk(tmp_path, "pathly/features/myfeat/plans")
    res = find_topic_dir(tmp_path, "myfeat")
    assert res == (tmp_path / "pathly" / "features" / "myfeat" / "plans", "team")


def test_find_topic_falls_back_to_legacy(tmp_path):
    _mk(tmp_path, "pathly/plans/legacyfeat")
    res = find_topic_dir(tmp_path, "legacyfeat")
    assert res == (tmp_path / "pathly" / "plans" / "legacyfeat", "team")


def test_most_recent_reports_feature_name_not_plans(tmp_path):
    _mk(tmp_path, "pathly/plans/older")
    b = _mk(tmp_path, "pathly/features/newer/plans")
    later = time.time() + 10
    os.utime(b / "STATE.json", (later, later))
    res = find_most_recent_state(tmp_path)
    assert res is not None
    storage, topic, _flow = res
    assert topic == "newer"  # not "plans"
    assert storage == tmp_path / "pathly" / "features" / "newer" / "plans"
