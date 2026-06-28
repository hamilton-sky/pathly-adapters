"""Shared Blueprint, constants, and helpers for the skills editor routes."""

from __future__ import annotations

import re

from flask import Blueprint

bp = Blueprint("skills", __name__)

_SKILL_KEY_RE = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")

_SUMMARY_STYLES = {"gist", "topic-map", "detailed"}
_SUMMARY_FORMAT_BY_SKILL = {
    "development/summarize": "topic-map",
    "development/summarize-gist": "gist",
    "development/summarize-detailed": "detailed",
}


def _read_summary_format(style: str) -> str:
    """Read the output-format contract for a summary DEPTH style. Returns '' on unknown."""
    if style not in _SUMMARY_STYLES:
        return ""
    try:
        from importlib.resources import files as _res_files

        return (
            _res_files("pathly_data")
            .joinpath(f"core/templates/summary/{style}.md")
            .read_text(encoding="utf-8")
            .strip()
        )
    except Exception:
        return ""
