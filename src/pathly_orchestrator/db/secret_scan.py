"""Find and redact run tokens in text before Pathly stores it.

The server keeps only ``sha256`` of each run token (``queries/run_tokens.py``), and an
``AGENT_DONE`` can arrive without a token or be written by the agent's own process, so the raw
token is never at hand where text is stored. The scan instead hashes every 43-character window
(``secrets.token_urlsafe(32)``'s length) of each run of URL-safe characters and looks the hashes
up in ``run_tokens`` (any run, revoked or not). It also takes whatever follows
``PATHLY_RUN_TOKEN=`` or ``PATHLY_RUN_TOKEN:``, but never a shell reference such as
``$PATHLY_RUN_TOKEN`` (stored prompts carry those). Text with no 43-character run and no
``PATHLY_RUN_TOKEN`` costs one regex search and no query.

``contains_secret_hash`` is the same window test against one known hash (the chief's hook
secret). A token that was re-encoded (base64, split, reversed) is not found.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any, Iterator

REDACTED = "[run token]"
TOKEN_LENGTH = 43  # len(secrets.token_urlsafe(32))
_ENV_NAME = "PATHLY_RUN_TOKEN"

_RUN = re.compile(r"[A-Za-z0-9_-]{%d,}" % TOKEN_LENGTH)
# The name not inside a shell reference ($NAME, ${NAME...}), then = or :, an optional quote,
# and a value that is not a shell reference ($...) or an earlier redaction ([run token]).
# A backslash ends the value so a JSON-escaped quote is never cut in half.
_ENV = re.compile(
    r"(?<![$\w{])(PATHLY_RUN_TOKEN[=:][ \t]*[\"']?)(?![$\[])([^\s\"'`\\]+)"
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _windows(text: str) -> Iterator[str]:
    for match in _RUN.finditer(text):
        run = match.group(0)
        for start in range(len(run) - TOKEN_LENGTH + 1):
            yield run[start : start + TOKEN_LENGTH]


def _worth_scanning(text: str) -> bool:
    return bool(text) and (_ENV_NAME in text or _RUN.search(text) is not None)


def _known_windows(conn: sqlite3.Connection, text: str) -> list[str]:
    """The windows of ``text`` whose hash is a run token's, in order of first appearance."""
    by_hash: dict[str, str] = {}
    for window in _windows(text):
        by_hash.setdefault(_sha256(window), window)
    if not by_hash:
        return []
    try:
        rows = conn.execute(
            "SELECT token_hash FROM run_tokens "
            "WHERE token_hash IN (SELECT value FROM json_each(?))",
            (json.dumps(list(by_hash)),),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []  # a database with no run_tokens table has issued no token
        raise
    known = {row[0] for row in rows}
    return [window for digest, window in by_hash.items() if digest in known]


def find_run_tokens(conn: sqlite3.Connection, text: str) -> list[str]:
    """Every run token in ``text``: env-pattern values first, then known 43-character windows."""
    if not _worth_scanning(text):
        return []
    found = [m.group(2) for m in _ENV.finditer(text)]
    found += [w for w in _known_windows(conn, text) if w not in found]
    return list(dict.fromkeys(found))


def redact_run_tokens(conn: sqlite3.Connection, text: str) -> str:
    """``text`` with each run token replaced by ``[run token]`` (falsy text is returned as is)."""
    if not _worth_scanning(text):
        return text
    text = _ENV.sub(lambda m: m.group(1) + REDACTED, text)
    for token in _known_windows(conn, text):
        text = text.replace(token, REDACTED)
    return text


def redact_value(conn: sqlite3.Connection, value: Any) -> Any:
    """``value`` with every string inside it (dict values, list items) redacted.

    Returns the same object when nothing changed, so a caller's dict is never copied for
    nothing; dict keys are left as they are.
    """
    if isinstance(value, str):
        redacted_text = redact_run_tokens(conn, value)
        return value if redacted_text == value else redacted_text
    if isinstance(value, dict):
        items = {k: redact_value(conn, v) for k, v in value.items()}
        changed = any(items[k] is not value[k] for k in value)
        return items if changed else value
    if isinstance(value, (list, tuple)):
        redacted = [redact_value(conn, v) for v in value]
        if all(new is old for new, old in zip(redacted, value)):
            return value
        return type(value)(redacted)
    return value


def contains_secret_hash(text: str, sha256_hex: str) -> bool:
    """Whether any 43-character window of a URL-safe run in ``text`` hashes to ``sha256_hex``."""
    if not text or not sha256_hex:
        return False
    return any(_sha256(window) == sha256_hex for window in _windows(text))
