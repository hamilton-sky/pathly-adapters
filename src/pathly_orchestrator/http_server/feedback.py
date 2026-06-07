"""Feedback file watcher and processing helpers."""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

logger = logging.getLogger("pathly.http")

_ARCH_QUESTION = re.compile(
    r"\b(architect|architecture|architectural|design|approach|structure)\b",
    re.IGNORECASE,
)
_TTL_KEY = "ttl_hours"
_TTL_LINE = "ttl_hours: 48"
_FENCE = "---"


def _classify_content(content: str) -> str:
    lines = content.splitlines()
    tagged = []
    for line in lines:
        stripped = line.strip()
        if (
            stripped.startswith("- ")
            and not stripped.startswith("- [REQ]")
            and not stripped.startswith("- [ARCH]")
        ):
            question_text = stripped[2:]
            if _ARCH_QUESTION.search(question_text):
                tagged.append(f"- [ARCH] {stripped[2:]}")
            else:
                tagged.append(f"- [REQ] {stripped[2:]}")
        else:
            tagged.append(line)
    return "\n".join(tagged) + "\n"


def _has_ttl(content: str) -> bool:
    lines = content.splitlines()
    in_frontmatter = False
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == _FENCE:
            in_frontmatter = True
            continue
        if in_frontmatter:
            if line.strip() == _FENCE:
                break
            if line.startswith(_TTL_KEY + ":"):
                return True
    return False


def _inject_ttl(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].strip() == _FENCE:
        return _FENCE + "\n" + _TTL_LINE + "\n" + "\n".join(lines[1:]) + "\n"
    return _FENCE + "\n" + _TTL_LINE + "\n" + _FENCE + "\n" + content


def _process_feedback_file(path: Path) -> None:
    try:
        content = path.read_text(encoding="utf-8")
        if not _has_ttl(content):
            content = _inject_ttl(content)
        content = _classify_content(content)
        path.write_text(content, encoding="utf-8")
    except OSError:
        logger.warning("feedback file write failed: %s", path, exc_info=True)


def _feedback_watcher(project_root: str, stop: threading.Event) -> None:
    plans_dir = Path(project_root) / "pathly" / "plans"
    seen: dict[Path, float] = {}
    while not stop.is_set():
        try:
            for md_file in plans_dir.glob("*/feedback/*.md"):
                mtime = md_file.stat().st_mtime
                if seen.get(md_file) != mtime:
                    seen[md_file] = mtime
                    _process_feedback_file(md_file)
        except Exception:
            logger.warning("feedback watcher error", exc_info=True)
        stop.wait(2.0)
