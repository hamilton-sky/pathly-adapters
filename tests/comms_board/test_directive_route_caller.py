"""chief-agent 20, B14: a directive is stamped with the caller that was checked.

``POST /comms/directives`` asked ``caller_identity(request)`` once to check the caller is a live
chief and again to stamp the row. If the token was revoked between the two (the session closes),
the second answer was "no identity" and the row was stored with ``author_source`` ``none``. The
route now looks the identity up once and uses it for both.
"""

from __future__ import annotations

import pytest
from chief_human_support import (
    _no_watcher_outlives_its_test,
    chief_root,
    client,
    host,
    open_session,
    project,
)
from directives_support import _post, _recency_path, _row
from mirror_drain_support import _mirrors_are_drained

from pathly_orchestrator.http_server.blueprints.comms import directives
from pathly_orchestrator.http_server.run_identity import CallerIdentity


def _identity_that_changes_after_the_first_lookup(monkeypatch) -> list[CallerIdentity]:
    """The first lookup answers as the real function does; every later one is anonymous (the
    session closed in between). Returns the list the answers are appended to."""
    real = directives.caller_identity
    answers: list[CallerIdentity] = []

    def lookup(request) -> CallerIdentity:
        answer = real(request) if not answers else CallerIdentity(kind="anonymous")
        answers.append(answer)
        return answer

    monkeypatch.setattr(directives, "caller_identity", lookup)
    return answers


def test_the_route_looks_the_caller_up_once_and_stamps_with_what_it_checked(
    client, project, chief_root, monkeypatch
):
    opened = open_session(project, chief_root)
    answers = _identity_that_changes_after_the_first_lookup(monkeypatch)

    resp = _post(client, opened, to_agent="builder")

    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert len(answers) == 1
    row = _row(resp.get_json()["id"])
    assert (row["author_role"], row["author_run_id"], row["author_source"]) == (
        "chief",
        opened.run_id,
        "token",
    )


def test_a_caller_that_is_not_a_chief_at_the_first_lookup_is_still_refused(
    client, project, chief_root, monkeypatch
):
    opened = open_session(project, chief_root)
    calls: list[int] = []

    def anonymous(request) -> CallerIdentity:
        calls.append(1)
        return CallerIdentity(kind="anonymous")

    monkeypatch.setattr(directives, "caller_identity", anonymous)

    resp = _post(client, opened, to_agent="builder")

    assert resp.status_code == 403
    assert len(calls) == 1
