"""The chief's argv and claude settings (pure: no I/O, no prompt, no token).

The chief is a long-lived interactive session, so it does not use ``argv.resolve_interactive_argv``
(which always adds ``--model`` and, by default, a permission-bypass flag). Its argv carries only
what keeps the chief inside its permissions; the prompt is pasted by the spawn host afterwards and
the run token reaches the process through ``PATHLY_RUN_TOKEN``, never through argv.
"""

from __future__ import annotations

CLAUDE_TOOLS = "Bash,Read,Glob,Grep"

_CLAUDE_ALLOW = ["Bash(pathly *)"]
_CLAUDE_DENY = [
    "Edit",
    "Write",
    "NotebookEdit",
    "Agent",
    "CronCreate",
    "Workflow",
    "WebFetch",
    "WebSearch",
    "Read(~/.pathly/**)",
    "Bash(curl *)",
    "Bash(wget *)",
]
# claude 2.1.304 (measured): the first stops the ``<task-notification>`` prompts of background
# tasks, the second stops the scheduler that fires ``.claude/scheduled_tasks.json`` as a bare prompt.
# A permission rule does neither, so the settings carry them as an ``env`` block.
_CLAUDE_ENV = {
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
    "CLAUDE_CODE_DISABLE_CRON": "1",
}


def chief_argv(
    engine: str,
    model: str,
    settings_path: str,
    mcp_path: str,
    session_id: str | None,
) -> list[str]:
    """The argv that starts a chief on ``engine``; any other engine is a ``ValueError``.

    claude starts in restricted mode: ``--restricted`` ignores the user's, the project's and
    the local settings files (their allow rules would merge into the chief's), and ``--tools``
    leaves it Bash (for ``pathly``), Read, Glob and Grep. ``--strict-mcp-config`` with an empty
    config file keeps every MCP server away from it. codex runs in a read-only sandbox and asks
    before every command; it has no session id to choose, so ``session_id`` is ignored.
    """
    if engine == "claude":
        if not session_id:
            raise ValueError("a claude chief needs the session id the server chose")
        argv = [
            "claude",
            "--restricted",
            "--tools",
            CLAUDE_TOOLS,
            "--settings",
            settings_path,
            "--mcp-config",
            mcp_path,
            "--strict-mcp-config",
            "--session-id",
            session_id,
        ]
    elif engine == "codex":
        argv = ["codex", "--sandbox", "read-only", "--ask-for-approval", "on-request"]
    else:
        raise ValueError(f"the chief runs on claude or codex, not {engine!r}")
    if model:
        argv.extend(["--model", model])
    return argv


def claude_settings(hook_command: str) -> dict:
    """The session's claude settings: ``pathly`` commands allowed, the rest denied or asked.

    Only ``Bash(pathly *)`` is allowed ahead of time, and ``curl`` and ``wget`` are denied. For
    every other Bash command these settings say nothing, so claude applies its own rule under
    ``--restricted --tools``: a read-only command (``ls``, ``git status``) runs without asking
    and the rest ask the human in the tab. That rule is claude's, not one of these settings, and
    it has not been run against this argv in a real tab yet (spike 19 part B, question 1). Most
    denied tools are already absent under ``--tools``; the rules stay so they still hold if a
    claude version reads ``--tools`` differently. One ``UserPromptSubmit`` hook runs
    ``hook_command``. An ``env`` block turns off background-task notifications and the cron
    scheduler (``_CLAUDE_ENV``), the two ways claude starts a turn nobody typed; measured on
    claude 2.1.304 only.
    """
    return {
        "permissions": {"allow": list(_CLAUDE_ALLOW), "deny": list(_CLAUDE_DENY)},
        "env": dict(_CLAUDE_ENV),
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": hook_command}]}
            ]
        },
    }
