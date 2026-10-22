"""UserPromptSubmit hook of a claude chief session: record what the human types (chief-agent).

Claude Code runs ``<python> -m pathly_hooks.chief_prompt --run-id <id> --secret-file <path>
--port <port>`` (the command ``supervisor/chief_session.py`` writes into the session's claude
settings) for every prompt the chief's claude receives, and passes the event as JSON on stdin:
``prompt`` and ``session_id`` are the two fields used here. The hook posts them with the
session's hook secret to ``POST /chief/human-messages``; the server stores the prompt and only
accepts it from the chief's own claude session. For a message stored as ``human`` the hook
prints one line, which Claude Code adds to the chief's context, naming the id to cite. The
session's first prompt (the pasted style) and a ``relayed`` one print nothing.

The hook is also run for prompts nobody typed, and nothing in the hook input says which: the
same keys and values arrive for a typed prompt and for the two below (measured on claude 2.1.304,
in ``claude -p`` stream-json and in an interactive tab). What differs is a wrapper around
``prompt``, so a prompt holding one of these tags anywhere is sent with ``relayed: true``, the
server stores it as ``relayed`` and it can never be cited. A tag counts when it starts with the
name, so ``<task-notifications>`` and ``<task-notification_v2>`` do too (the list cannot know
every spelling claude may use):

* ``<task-notification>``: claude's message when a background task ends. A chief can start one
  (Bash with ``run_in_background``, or a foreground command that hits its timeout), and the
  Bash call's ``description`` comes back inside ``<summary>``, so the chief chooses words in
  it. The same tag wraps the stall check ("appears to be waiting for interactive input"),
  which puts the command's own output after the closing tag.
* ``<cross-session-message ...>``: a message another claude session sends. A ``--restricted``
  claude binds no inbox, so none reaches the chief that way; the check is a second line.

That is a deny-list of the wrappers measured, not a test for "typed": a prompt without a tag is
stored as ``human`` whether or not anyone typed it. Measured on 2.1.304, a task in the
project's ``.claude/scheduled_tasks.json`` fires in the chief's tab as a bare prompt. The
chief cannot write that file, another process of the same user can; ``CLAUDE_CODE_DISABLE_CRON``
and ``CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`` close it and the notifications above, and the
settings of a claude chief set both (``runner/chief_argv.claude_settings``; see
``src/pathly_orchestrator/CLAUDE.md``, "Human messages"). A typed prompt that happens to hold a
tag is wrongly uncitable, which the human repairs by retyping; the other mistake would let
another party's words pass as the human's.

The hook never blocks or alters the prompt: bad stdin, bad arguments, a missing secret file, a
server that is down, a 403 or a stdout nobody reads all end in exit 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from pathly_orchestrator.fsm_http_client import DEFAULT_HOST, _request_json

PATH = "/chief/human-messages"
TIMEOUT_SECONDS = 5.0
CITE_LINE = (
    "Pathly recorded this as human message {id}; "
    "cite it with cite={id} when you relay an answer."
)
_NOT_TYPED = re.compile(r"<(?:task-notification|cross-session-message)")


class _Args(argparse.ArgumentParser):
    def error(self, message: str):
        raise ValueError(message)


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = _Args(prog="chief_prompt", add_help=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--secret-file", required=True)
    parser.add_argument("--port", required=True, type=int)
    return parser.parse_args(argv)


def _read_stdin() -> str:
    """The hook's stdin as text. Claude Code writes UTF-8 whatever the locale says."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is None:
        return sys.stdin.read()
    return buffer.read().decode("utf-8-sig")


def _prompt_and_session(raw: str) -> tuple[str, str] | None:
    event = json.loads(raw)
    if not isinstance(event, dict):
        return None
    prompt, session_id = event.get("prompt"), event.get("session_id")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    if not isinstance(session_id, str) or not session_id:
        return None
    return prompt, session_id


def _is_human(reply: object) -> bool:
    if not isinstance(reply, dict) or reply.get("kind") != "human":
        return False
    return isinstance(reply.get("id"), int) and not isinstance(reply.get("id"), bool)


def _record(argv: list[str]) -> str:
    """Post the prompt; the line to print, or "" when there is nothing to say."""
    args = _parse(argv)
    found = _prompt_and_session(_read_stdin())
    if found is None:
        return ""
    prompt, session_id = found
    secret = Path(args.secret_file).read_text(encoding="utf-8").strip()
    if not secret:
        return ""
    payload: dict = {
        "run_id": args.run_id,
        "hook_secret": secret,
        "text": prompt,
        "session_id": session_id,
    }
    if _NOT_TYPED.search(prompt):
        payload["relayed"] = True
    reply = _request_json(
        "POST",
        PATH,
        payload,
        host=DEFAULT_HOST,
        port=args.port,
        timeout=TIMEOUT_SECONDS,
    )
    return CITE_LINE.format(id=reply["id"]) if _is_human(reply) else ""


def _say(line: str) -> None:
    """Print ``line``. With no reader on stdout (a closed pipe) point it at the null device,
    so the flush at exit does not fail either."""
    try:
        print(line, flush=True)
    except OSError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


def main(argv: list[str] | None = None) -> int:
    """Run the hook; always returns 0."""
    try:
        line = _record(sys.argv[1:] if argv is None else argv)
        if line:
            _say(line)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
