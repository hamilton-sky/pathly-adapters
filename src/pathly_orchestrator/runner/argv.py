"""Argument resolution for runner subprocesses."""

from __future__ import annotations

from pathlib import Path

import yaml
from importlib.resources import files

from pathly_orchestrator.adapters import resolve_command


def _storage_path(flow: str, project_root: str, topic: str) -> Path:
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    flow_config = yaml.safe_load(text)
    template = flow_config["storage_path"]
    return Path(project_root) / template.format(topic=topic)


def resolve_interactive_argv(
    adapter: str,
    model: str,
    session: str | None = None,
    autonomy: bool = True,
) -> list[str]:
    """Build argv that opens the adapter interactively — no -p, no --output-format.
    The prompt is injected later via PTY stdin (bracketed paste)."""
    if adapter == "claude":
        argv = ["claude", "--model", model]
        if autonomy:
            argv.append("--dangerously-skip-permissions")
        if session:
            argv.extend(["--resume", session])
        return argv
    if adapter == "codex":
        argv = ["codex", "--model", model]
        if autonomy:
            argv.extend(["--sandbox", "workspace-write"])
        return argv
    return [adapter]


def resolve_argv(
    adapter: str,
    prompt: str,
    model: str,
    session: str | None = None,
    autonomy: bool = True,
    interactive: bool = False,
) -> list[str]:
    argv = resolve_command(
        adapter,
        prompt,
        model,
        session=session,
        autonomy=autonomy,
    )["argv"]
    if adapter == "claude" and "--output-format=json" not in argv and not interactive:
        argv = [*argv, "--print", "--output-format=json"]
    return argv
