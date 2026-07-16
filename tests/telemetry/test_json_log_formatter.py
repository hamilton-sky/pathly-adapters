"""Regression: the JSON log formatter must not crash on non-serializable args.

A third-party library (httpx, used by huggingface_hub during the embedding-model
download) logs HTTP requests with a URL *object* in record.args. The formatter
must not let that reach json.dumps unguarded, and must not leak standard
LogRecord attributes (like `args`) into the structured output.
"""

import json
import logging

from pathly_orchestrator.http_server.middleware import _JsonFormatter


class _Url:
    """Stand-in for httpx.URL — only str()-able, not JSON-serializable."""

    def __str__(self) -> str:
        return "https://example.com/x"


def test_formatter_survives_non_serializable_args():
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="HTTP Request: %s %s",
        args=("HEAD", _Url()),
        exc_info=None,
    )
    out = _JsonFormatter().format(record)  # must not raise
    parsed = json.loads(out)  # must be valid JSON
    assert parsed["msg"] == "HTTP Request: HEAD https://example.com/x"
    # Standard attributes must NOT leak into the structured payload.
    assert "args" not in parsed


def test_formatter_keeps_genuine_extra_fields():
    record = logging.LogRecord("x", logging.INFO, "", 0, "hi", None, None)
    record.feature = "demo"  # a real `extra=` field
    parsed = json.loads(_JsonFormatter().format(record))
    assert parsed["feature"] == "demo"
    assert parsed["msg"] == "hi"
    assert parsed["level"] == "INFO"
