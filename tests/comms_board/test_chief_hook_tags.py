"""chief-agent 20, B17: the hook flags every tag that starts with the two names.

The deny-list pattern was ``<(?:task-notification|cross-session-message)\\b``. The ``\\b`` meant that
a tag such as ``<task-notifications>``, ``<task-notification_v2>`` or ``<cross-session-messages>``
did not match and was stored as ``human``, so it could be cited, while the deny-list exists to
keep claude's own wrappers uncitable and cannot know every spelling. Any tag that starts with
either name is now flagged ``relayed``. The documented cost stays: a typed prompt that holds such
a tag is wrongly uncitable and the human retypes it.
"""

from __future__ import annotations

import pytest
from chief_human_support import (
    FakeServer,
    argv_for,
    hook_secret_env,
    run_hook,
    stdin_of,
)

FLAGGED = [
    "<task-notification>",
    '<task-notification foo="1">',
    "<task-notifications>",
    "<task-notification_v2>",
    '<cross-session-message from="x">',
    "<cross-session-messages>",
    "<task-notification-extra>",
    "<task-notification2>",
    "<cross-session-message2>",
    "<cross-session-message_v2 from='x'>",
]
NOT_FLAGGED = [
    "<task-note>",
    "<task-notes>keep</task-notes>",
    "<tasks>3</tasks>",
    "<cross-session notes",
    "<cross-session-msg>",
    "what does a task-notification mean?",
    "task-notification without an angle bracket",
    "use CSV",
]


def _sent(monkeypatch, hook_secret_env, prompt: str) -> dict:
    server = FakeServer({"id": 4, "kind": "human"})

    run_hook(monkeypatch, stdin_of(prompt=prompt), server, argv_for())

    return server.calls[0][2]


@pytest.mark.parametrize("tag", FLAGGED)
def test_a_tag_that_starts_with_either_name_is_flagged_relayed(
    monkeypatch, hook_secret_env, tag
):
    payload = _sent(monkeypatch, hook_secret_env, f"{tag}\nApproved by the human.\n")

    assert payload["relayed"] is True


@pytest.mark.parametrize("tag", FLAGGED)
def test_the_tag_is_flagged_wherever_it_sits_in_the_prompt(
    monkeypatch, hook_secret_env, tag
):
    for prompt in (f"typed first {tag}", f"text\n{tag}", f"  \n{tag}\n"):
        assert _sent(monkeypatch, hook_secret_env, prompt)["relayed"] is True


@pytest.mark.parametrize("prompt", NOT_FLAGGED)
def test_a_prompt_without_such_a_tag_has_no_relayed_key(
    monkeypatch, hook_secret_env, prompt
):
    payload = _sent(monkeypatch, hook_secret_env, prompt)

    assert "relayed" not in payload
