"""Every curl to the board under core/ must send the per-run token header (SPEC C4)."""

import re
import shutil
from pathlib import Path

from tests._paths import SRC

CORE = SRC / "pathly_data" / "core"
HEADER = 'X-Pathly-Run-Token: $PATHLY_RUN_TOKEN'


def missing_header(root: Path) -> list[str]:
    bad = []
    for path in sorted(root.rglob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "curl" not in line or "8765/comms" not in line:
                continue
            cmd, j = line, i
            while cmd.rstrip().endswith("\\") and j + 1 < len(lines):
                j += 1
                cmd += "\n" + lines[j]
            if HEADER not in cmd:
                bad.append(f"{path.relative_to(root)}:{i + 1}")
    return bad


def test_every_board_curl_sends_run_token():
    assert missing_header(CORE) == []


def test_check_detects_a_removed_header(tmp_path):
    copy = tmp_path / "core"
    shutil.copytree(CORE, copy)
    target = copy / "skills" / "fragments" / "comms-post.md"
    text = target.read_text(encoding="utf-8")
    assert HEADER in text
    target.write_text(re.sub(r'-H "X-Pathly-Run-Token[^"]*" ', "", text, count=1), encoding="utf-8")
    assert missing_header(copy) != []
