"""What a feedback spawn's prompt shows of the feedback file it is handed.

A gate or a reviewer writes a feedback file into ``<storage>/feedback/`` and the flow routes it to
a role. ``read_feedback`` is the one rule for how much of that file a prompt shows, shared by the
retry ladder block and by ``feedback_block``, the ``## Feedback to resolve`` section a first-round
feedback prompt carries (the ladder carries the text from the second round on).
"""

from __future__ import annotations

import re
from pathlib import Path

FEEDBACK_LIMIT = 4000


def feedback_path(storage_path: Path, feedback_file: str) -> str:
    """``<storage>/feedback/<file>``, the way a prompt names the file (forward slashes)."""
    return "%s/feedback/%s" % (storage_path.as_posix().rstrip("/"), feedback_file)


def _read_whole(storage_path: Path, feedback_file: str) -> str:
    """The file's whole text, stripped; ``""`` when it cannot be read (missing, not text)."""
    try:
        return (
            (storage_path / "feedback" / feedback_file)
            .read_text(encoding="utf-8")
            .strip()
        )
    except (OSError, UnicodeError):
        return ""


def read_feedback(storage_path: Path, feedback_file: str) -> str:
    """The file's text, stripped and clipped to ``FEEDBACK_LIMIT`` characters.

    ``""`` when it cannot be read (missing, not text) or holds nothing but whitespace.
    """
    return _read_whole(storage_path, feedback_file)[:FEEDBACK_LIMIT]


def feedback_block(storage_path: Path, feedback_file: str) -> str:
    """The ``## Feedback to resolve`` section: the file's path and its text in a code fence.

    The path is the one the Fix mode block uses. The fence is one backtick longer than any run of
    backticks in the text, since these files quote failing command output. A file longer than
    ``FEEDBACK_LIMIT`` is cut, and the block says so and points at the full file.
    """
    path = feedback_path(storage_path, feedback_file)
    whole = _read_whole(storage_path, feedback_file)
    text = whole[:FEEDBACK_LIMIT]
    head = (
        "\n## Feedback to resolve\n\n"
        "`%s` is what the gate or reviewer wrote when this stage was sent back. "
        "Fix the cause it describes, not the file.\n" % path
    )
    if not text:
        return head + (
            "\nIts text could not be read (the file is missing, unreadable or empty). "
            "Look at the file yourself before you change anything.\n"
        )
    runs = [len(run) for run in re.findall(r"`+", text)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    block = head + "\n%s\n%s\n%s\n" % (fence, text, fence)
    if len(whole) > FEEDBACK_LIMIT:
        block += (
            "\nThat is the first %d characters of the file. Read the rest at `%s` "
            "before you change anything.\n" % (FEEDBACK_LIMIT, path)
        )
    return block
