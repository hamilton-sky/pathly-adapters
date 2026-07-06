"""Resolve a CLI command for a given adapter from core/adapters.yaml."""

from __future__ import annotations

import re
from importlib.resources import files
from typing import Optional

import yaml

# The prompt is substituted into the headless argv. For claude it lands as a bare
# positional after -p/--print, so a prompt starting with "--" is parsed as an
# unknown option ("error: unknown option '---...'"). Strip a leading
# YAML-frontmatter / horizontal-rule block so the prompt can NEVER start with a
# dash — regardless of source (composed skill, raw/absent skill, DAG task text).
_LEADING_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n.*?\n---[ \t]*\n", re.DOTALL)


def _dash_safe_prompt(prompt: str) -> str:
    """Remove a leading frontmatter / '---' block so the prompt never starts with '-'."""
    p = prompt.lstrip()
    m = _LEADING_FRONTMATTER_RE.match(p)
    if m:
        p = p[m.end() :].lstrip()
    # Any remaining leading horizontal-rule lines with no closing pair.
    p = re.sub(r"^(?:-{3,}[ \t]*\n\s*)+", "", p)
    return p


def _load_adapters() -> dict:
    text = (
        files("pathly_data").joinpath("core/adapters.yaml").read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


# Which model families each engine can run. A model outside its engine's family fails
# at the provider with a cryptic 400 ("The 'claude-sonnet-4-6' model is not supported when
# using Codex with a ChatGPT account") and silently produces no output — validate_adapter_model
# rejects it LOUDLY at dispatch instead. copilot proxies multiple providers (unconstrained);
# an empty model means the engine's own default.
_ADAPTER_MODEL_PREFIXES: dict[str, tuple[str, ...]] = {
    "claude": ("claude-",),                                   # Anthropic: opus / sonnet / haiku / fable
    "codex": ("gpt-", "o1-", "o3-", "o4-", "o5-", "codex-"),  # OpenAI GPT / o-series
    "antigravity": ("gemini-",),                              # Google Gemini (agy)
    "copilot": (),                                            # multi-provider proxy — unconstrained
}


def _engine_for_model(model: str) -> str:
    """The engine whose model-family ``model`` belongs to, or '' if unrecognized."""
    m = (model or "").strip().lower()
    for adapter, prefixes in _ADAPTER_MODEL_PREFIXES.items():
        if prefixes and any(m.startswith(p) for p in prefixes):
            return adapter
    return ""


def validate_adapter_model(adapter: str, model: str | None) -> str | None:
    """Return a human error reason if ``model`` cannot run on ``adapter``, else None.

    An empty model (engine default) always passes. An unknown adapter or copilot (a
    multi-provider proxy) is unconstrained. Only a KNOWN, constrained adapter with a model
    outside its family is rejected — with a hint at the engine that model DOES run on.
    """
    a = (adapter or "").strip().lower()
    m = (model or "").strip().lower()
    if not m:
        return None
    prefixes = _ADAPTER_MODEL_PREFIXES.get(a)
    if not prefixes:  # unknown adapter or unconstrained proxy (copilot)
        return None
    if any(m.startswith(p) for p in prefixes):
        return None
    # Only reject when the model CLEARLY belongs to another known engine. An
    # unrecognized model (a custom or newly-released name) is allowed — don't guess.
    right = _engine_for_model(m)
    if not right:
        return None
    return (
        f"model {model!r} can't run on the {adapter!r} engine "
        f"(it runs {'/'.join(prefixes)} models) — use the {right!r} engine for that model"
    )


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

    # Reject a model that can't run on this engine LOUDLY here, instead of letting the
    # CLI 400 mid-run and silently produce nothing (the failure mode that made a Codex
    # run with a claude model seed no DAG).
    _mismatch = validate_adapter_model(adapter, model)
    if _mismatch:
        raise ValueError(f"adapter_model_mismatch: {_mismatch}")

    headless = cfg.get("headless")
    if headless is None:
        raise ValueError(
            f"Adapter {adapter!r} has no headless mode (headless: null). "
            "Cannot build a command argv for it."
        )

    resume_cfg = cfg.get("resume")
    supports_resume = resume_cfg is not None
    terminal_kind = cfg.get("terminal_kind", adapter)

    prompt = _dash_safe_prompt(prompt)
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


def headless_capable(adapter: str) -> bool:
    """True if *adapter* exists and has a headless template (can run a one-shot in the runner)."""
    cfg = _load_adapters().get(adapter)
    return bool(cfg and cfg.get("headless"))


def unsupported_headless_adapters(adapters: list[str]) -> list[str]:
    """Return the sorted, de-duplicated subset of *adapters* that cannot run headless.

    An adapter is unsupported if it is unknown or declares ``headless: null``. Used at
    run-start to reject a flow whose adapter_map routes a stage to a CLI with no headless
    mode, instead of letting resolve_command raise opaquely mid-pipeline.
    """
    return sorted({a for a in adapters if a and not headless_capable(a)})
