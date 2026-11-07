"""The hook-secret check of the chief gate (chief-autopilot 02): a body never carries it.

The ``UserPromptSubmit`` hook sends the session's hook secret with each prompt it records as typed
by the person. No file holds it: it is in the chief claude's environment
(``PATHLY_CHIEF_HOOK_SECRET``, claimed once by Studio with ``POST /chief/hook-secret``), and the
chief's settings deny it ``env``, ``printenv`` and reads of ``/proc``
(``runner/chief_argv.claude_settings``); this check is defence in depth. A chief-token request any
of whose JSON string values, at any depth, holds the session's own hook secret is refused (400)
before the cite and budget checks, so nothing is stored, no citation is spent and no run slot is
taken. That covers the text, goal and task fields of ``/comms/post``, the text of
``/comms/directives``, ``/comms/acknowledge`` and ``/runner/agent-answer``, and every other route a
chief may write.

The scan is ``db/secret_scan.contains_secret_hash`` against ``chief_sessions.hook_secret_hash``:
every 43-character window of each URL-safe run is hashed, so the secret inside a longer run
(``x<secret>``) is caught. A re-encoded secret (base64 of it, split in two, reversed) is not, nor
a slice the shell expands from ``$PATHLY_CHIEF_HOOK_SECRET`` inside an allowed ``pathly api``
body, which the deny rules do not stop either: neither is a guarantee. A session with no stored
hash (a codex chief) is not checked.
"""

from __future__ import annotations

from typing import Iterator, Mapping, Sequence

SECRET_IN_BODY = "the body contains this chief's hook secret"


def _strings(value: object) -> Iterator[str]:
    """Every string value inside ``value``: dicts and lists are walked, keys are not."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def secret_refusal(session: Mapping, bodies: Sequence[Mapping]) -> str | None:
    """``SECRET_IN_BODY`` when a reading of the body holds the session's hook secret, else None."""
    from pathly_orchestrator.db.secret_scan import contains_secret_hash

    sha256_hex = session.get("hook_secret_hash")
    if not isinstance(sha256_hex, str) or not sha256_hex:
        return None
    for body in bodies:
        for text in _strings(body):
            if contains_secret_hash(text, sha256_hex):
                return SECRET_IN_BODY
    return None
