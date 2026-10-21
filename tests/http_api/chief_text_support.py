"""Helpers of the tests that read the chief's prompt texts (chief-agent 17, round 2).

The chief's prompt is two parts: a built-in style (``status``, ``planner``, ``operator``) and the
``chief-connect`` fragment. ``text_of`` returns either; ``norm`` flattens one so a test can look for
a short phrase and stay green when a paragraph is re-wrapped or a word gets backticks; ``pathly_commands``
returns every ``pathly api METHOD TARGET`` of a text with its target as written (quotes kept), so a
test can tell a quoted path from a bare one.
"""

from __future__ import annotations

import re

from chief_cli_support import fragment_text

STYLES = ("status", "planner", "operator")
TEXT_NAMES = (*STYLES, "chief-connect")

COMMAND = re.compile(r"\bpathly api (GET|POST|PUT|DELETE) (\S+)")


def text_of(name: str) -> str:
    """A prompt text by name: a built-in style, or the ``chief-connect`` fragment."""
    if name == "chief-connect":
        return fragment_text()
    from pathly_orchestrator.supervisor import chief_presets

    return chief_presets.BUILT_IN[name]


def norm(text: str) -> str:
    """``text`` lower-cased, with backticks dropped and every run of white space one space."""
    return re.sub(r"\s+", " ", text.replace("`", "")).strip().lower()


def pathly_commands(text: str) -> list[tuple[str, str]]:
    """Each ``pathly api METHOD TARGET`` of a text, as (method, target as written)."""
    return COMMAND.findall(text)


def fenced_blocks(text: str) -> list[list[str]]:
    """The lines of each fenced block of a text, in order (blank lines left out)."""
    blocks: list[list[str]] = []
    inside = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            if inside:
                blocks.append([])
        elif inside and line.strip():
            blocks[-1].append(line.strip())
    return blocks
