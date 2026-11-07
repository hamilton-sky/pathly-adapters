"""What ``POST /comms/post`` checks in a ``type: task`` post's text and refs.

**Plan lint.** Every task the server proves needs something to prove: ``task_checks`` and
``task_proof`` run the task's ```check blocks, so a task posted with none has nothing to run.
``task_check_refusal`` is the one test: a task passes when its text holds a ```check block with
at least one command, or a line that starts ``Check: none`` and gives a reason. The route asks it
only for a planner run's task (a decompose); the person, the chief and every other role post as
before.

**ref_warning (T3a).** A task posted with no ``context_refs`` (and no explicit ``no_refs``
justification) falls back to unverified auto-derived context. ``ref_warning`` is the
NON-BLOCKING warning the route returns so the gap is visible to the poster instead of silently
degrading context quality (ISSUE-4).
"""

from __future__ import annotations

import re

NO_CHECK = 'task has no check block and no "Check: none <why>" line'
REASON = (
    "a decompose must post each task with its check block or a 'Check: none <why>' line"
)

# ``Check: none``, then an optional ``-``, ``—`` or ``:``, then the reason (the rest of the line).
_CHECK_NONE = re.compile(r"^Check: none(?:\s*[-—:]|(?=\s)|$)(?P<why>.*)$", re.MULTILINE)


def task_check_refusal(text: str) -> str | None:
    """None when the task has something to prove or says why not; else why it is refused."""
    from pathly_orchestrator.proof.checks import ParseError, checks_in

    try:
        if checks_in(text):
            return None
    except ParseError as exc:
        return str(exc)
    for found in _CHECK_NONE.finditer(text):
        if found.group("why").strip():
            return None
    return NO_CHECK


def decompose_refusal(identity, msg_type: str, text: str) -> dict | None:
    """The 422 body for a planner run's task that ``task_check_refusal`` refuses; else None.

    The role comes from the caller's live run token (``caller_identity``), never the body: a
    tokenless caller, a chief token and every other role are not linted.
    """
    if msg_type != "task" or identity.kind != "run" or identity.role != "planner":
        return None
    refusal = task_check_refusal(text)
    if refusal is None:
        return None
    return {"error": refusal, "reason": REASON, "task": task_title(text)}


def task_title(text: str) -> str:
    """The text's first line, at most 80 characters: names the refused task in the 422."""
    return text.strip().split("\n", 1)[0].strip()[:80]


def ref_warning(data: dict, context_refs) -> str | None:
    """The ref_warning of a task with no ``context_refs`` and no ``no_refs``; else None."""
    _has_refs = isinstance(context_refs, list) and len(context_refs) > 0
    if not _has_refs and not data.get("no_refs"):
        return (
            "task has no context_refs; agents will fall back to unverified "
            "auto-derived context — add context_refs or pass no_refs=<reason>"
        )
    return None
