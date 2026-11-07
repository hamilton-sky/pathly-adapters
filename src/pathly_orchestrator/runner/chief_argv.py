"""The chief's argv and claude settings (pure: no I/O, no prompt, no token).

The chief is a long-lived interactive session, so it does not use ``argv.resolve_interactive_argv``
(which always adds ``--model`` and, by default, a permission-bypass flag). Its argv carries only
what keeps the chief inside its permissions; the prompt is pasted by the spawn host afterwards and
the run token reaches the process through ``PATHLY_RUN_TOKEN``, never through argv.
"""

from __future__ import annotations

CLAUDE_TOOLS = "Bash,Read,Glob,Grep"
# claude 2.1.310 (spike 19 part B, question 1): with no ``--permission-mode`` the chief started in
# auto mode despite ``--restricted``, and auto mode ran ``python3`` without asking. ``dontAsk``
# denies every call that would otherwise prompt.
CLAUDE_PERMISSION_MODE = "dontAsk"

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
    "Grep(~/.pathly/**)",
    "Glob(~/.pathly/**)",
    "Bash(curl *)",
    "Bash(wget *)",
    # The hook secret is in the chief claude's environment (PATHLY_CHIEF_HOOK_SECRET), so the
    # chief may not print it with these. They do not stop the shell expanding
    # $PATHLY_CHIEF_HOOK_SECRET (or a slice of it) inside an allowed ``pathly api`` body.
    # A single leading slash anchors a path rule at the settings source;
    # ``//`` is the filesystem root, so ``//proc/**`` is the rule that reaches /proc.
    "Bash(env*)",
    "Bash(printenv*)",
    "Read(/proc/**)",
    "Read(//proc/**)",
    "Grep(//proc/**)",
    "Glob(//proc/**)",
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
    leaves it Bash (for ``pathly``), Read, Glob and Grep. ``--permission-mode dontAsk``
    (``CLAUDE_PERMISSION_MODE``) denies every call that would otherwise prompt, instead of claude's
    auto mode, which approved arbitrary commands (spike 19, claude 2.1.310). ``--strict-mcp-config`` with an empty
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
            "--permission-mode",
            CLAUDE_PERMISSION_MODE,
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
    """The session's claude settings: ``pathly`` commands allowed, the rest denied.

    Only ``Bash(pathly *)`` is allowed ahead of time, and ``curl`` and ``wget`` are denied. For
    every other Bash command these settings say nothing, so claude applies its own rule under
    ``--restricted --tools --permission-mode dontAsk``: its built-in read-only commands (``ls``,
    ``git status``) run without asking in every mode, and every other command is denied without
    asking. That rule is claude's, not one of these settings, and it has not been re-measured
    against this argv in a real tab yet (spike 19 part B, question 1). Most
    denied tools are already absent under ``--tools``; the rules stay so they still hold if a
    claude version reads ``--tools`` differently. One ``UserPromptSubmit`` hook runs
    ``hook_command``. An ``env`` block turns off background-task notifications and the cron
    scheduler (``_CLAUDE_ENV``), the two ways claude starts a turn nobody typed; measured on
    claude 2.1.304 only.

    No file holds the hook secret: the hook reads it from claude's environment
    (``PATHLY_CHIEF_HOOK_SECRET``), so ``Bash(env*)`` and ``Bash(printenv*)`` are denied, and
    ``Read``, ``Grep`` and ``Glob`` on ``/proc`` (``//proc/**``, the filesystem root;
    ``Read(/proc/**)`` too, which claude anchors at the settings source). ``Read``, ``Grep`` and
    ``Glob`` stay denied on ``~/.pathly/**`` (the database; claude applies a ``Read`` rule to
    Grep, Glob, Bash file commands and ``< file`` redirects too; the explicit rules cost nothing)
    and ``blockReadsOutsideWorkingDirectories`` is set. There is no redirect rule:
    ``Bash(pathly *<*)`` would deny an ordinary body holding ``<``.
    """
    return {
        "permissions": {
            "allow": list(_CLAUDE_ALLOW),
            "deny": list(_CLAUDE_DENY),
            "blockReadsOutsideWorkingDirectories": True,
        },
        "env": dict(_CLAUDE_ENV),
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": hook_command}]}
            ]
        },
    }
