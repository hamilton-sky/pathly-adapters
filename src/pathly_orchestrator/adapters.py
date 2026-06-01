"""Resolve a CLI command for a given adapter from core/adapters.yaml."""

from __future__ import annotations

from importlib.resources import files
from typing import Optional

import yaml


def _load_adapters() -> dict:
    text = (
        files("pathly_data")
        .joinpath("core/adapters.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def resolve_command(
    adapter: str,
    prompt: str,
    model: str,
    session: Optional[str] = None,
    autonomy: bool = True,
) -> dict:
    """Return {argv, terminal_kind, supports_resume} for the given adapter.

    autonomy: when True and the adapter has an autonomy_flag, it is included.
    session: when provided and the adapter supports resume, the resume flag is spliced in.
    """
    config = _load_adapters()
    if adapter not in config:
        known = ", ".join(sorted(config.keys()))
        raise ValueError(f"Unknown adapter {adapter!r}. Known adapters: {known}")

    cfg = config[adapter]

    headless = cfg.get("headless")
    if headless is None:
        raise ValueError(
            f"Adapter {adapter!r} has no headless mode (headless: null). "
            "Cannot build a command argv for it."
        )

    resume_cfg = cfg.get("resume")
    supports_resume = resume_cfg is not None
    terminal_kind = cfg.get("terminal_kind", adapter)

    argv: list[str] = []
    for token in headless:
        token_str = str(token)
        token_str = token_str.replace("{prompt}", prompt)
        token_str = token_str.replace("{model}", model)
        argv.append(token_str)

    if autonomy and cfg.get("autonomy_flag"):
        argv.append(cfg["autonomy_flag"])

    if session and supports_resume:
        mode = resume_cfg.get("mode")
        flag = resume_cfg.get("flag")
        if mode == "flag" and flag:
            argv.append(flag)
            arg_template = resume_cfg.get("arg")
            if arg_template:
                argv.append(arg_template.replace("{session_id}", session))

    return {
        "argv": argv,
        "terminal_kind": terminal_kind,
        "supports_resume": supports_resume,
    }
