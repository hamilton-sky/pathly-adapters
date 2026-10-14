"""What the tasks a DAG task depends on produced, as a block for its prompt (build-proof).

A task agent used to see only its own text. The tasks it depends on are already done, and
each reported what it built in its ``AGENT_DONE`` summary; ``dependency_results_block`` puts
those summaries in front of the dependent task so it neither redoes nor guesses at them.
Only the direct ``depends_on`` ids are shown, not the dependencies' dependencies.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("pathly.task_dependencies")

RESULTS_HEADING = "## Results of the tasks this one depends on"
NO_RESULT = "(no result recorded)"
SUMMARY_LIMIT = 2000
BLOCK_LIMIT = 8000
_TITLE_LIMIT = 200


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _dependency_ids(task: dict) -> list[str]:
    """The task's direct ``depends_on`` ids, in order, without repeats."""
    raw = task.get("depends_on")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(str(dep) for dep in raw if dep))


def _title(row: dict | None, task_id: str) -> str:
    """The first non-blank line of a task's text, else its id."""
    for line in str((row or {}).get("text") or "").splitlines():
        if line.strip():
            return _clip(line.strip(), _TITLE_LIMIT)
    return task_id


def dependency_results_block(task: dict) -> str:
    """``\\n\\n## Results of the tasks this one depends on …``, or ``""``.

    One ``### `` heading per direct dependency (its first text line) followed by its latest
    ``AGENT_DONE`` summary clipped to 2000 characters, or ``(no result recorded)``; the whole
    block is clipped to 8000. A task without dependencies, or whose results cannot be read,
    gets ``""``, so its prompt is unchanged and a database hiccup never costs it the task.
    """
    dep_ids = _dependency_ids(task)
    if not dep_ids:
        return ""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import get_task
        from pathly_orchestrator.db.queries.task_results import latest_task_summaries

        conn = get_db()
        summaries = latest_task_summaries(conn, dep_ids)
        titles = {dep: _title(get_task(conn, dep), dep) for dep in dep_ids}
    except Exception:
        logger.debug("task_dependencies: results unreadable", exc_info=True)
        return ""
    parts = [RESULTS_HEADING]
    for dep in dep_ids:
        result = _clip(summaries[dep], SUMMARY_LIMIT) if dep in summaries else NO_RESULT
        parts.append(f"### {titles[dep]}\n\n{result}")
    return "\n\n" + _clip("\n\n".join(parts), BLOCK_LIMIT)
