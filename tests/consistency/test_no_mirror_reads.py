"""Run the state-one-authority mirror-read gate inside pytest too.

The same checker CI runs (scripts/check_no_mirror_reads.py): runtime code must
read the DB, never a STATE.json/EVENTS.jsonl/ARTIFACTS.jsonl/BOARD.json disk
mirror, except at marker-commented sites listed in scripts/mirror_reads_allowlist.txt.
"""

from __future__ import annotations

import importlib.util
import sys

from tests._paths import REPO_ROOT


def _load_checker():
    script = REPO_ROOT / "scripts" / "check_no_mirror_reads.py"
    spec = importlib.util.spec_from_file_location("check_no_mirror_reads", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_no_mirror_reads"] = module
    spec.loader.exec_module(module)
    return module


def test_no_unsanctioned_mirror_reads(capsys):
    checker = _load_checker()
    exit_code = checker.main()
    output = capsys.readouterr().out
    assert exit_code == 0, f"mirror-read gate failed:\n{output}"


def test_every_allowlist_entry_exists():
    checker = _load_checker()
    for rel in sorted(checker.load_allowlist()):
        assert (checker.ROOT / rel).exists(), f"allow-list entry missing on disk: {rel}"
