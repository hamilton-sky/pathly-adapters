"""Unit tests for the /code/query board-log line (observability).

The gateway logs each fresh code query to the project board so a human can SEE, in
the Command Center, which queries ran and whether they returned data. `backend=cli`
alone means the backend is *wired*; the `hit`/`miss` marker is what tells a watcher
the query got *usable structure* (or degraded to Grep). This locks that marker.
"""

from pathly_orchestrator.http_server.blueprints.code.query import _query_log_text


def test_log_text_marks_hit_when_backend_returned_data():
    line = _query_log_text("symbol", "scheduler.py", "builder", "cli", True)
    assert "code-query: symbol scheduler.py" in line
    assert "role=builder" in line
    assert "backend=cli" in line
    assert "hit" in line and "miss" not in line


def test_log_text_marks_miss_when_backend_empty():
    line = _query_log_text("impact", "foo.py", "reviewer", "cli", False)
    assert "backend=cli" in line
    assert "miss" in line


def test_log_text_defaults_missing_role():
    line = _query_log_text("symbol", "x.py", "", "none", False)
    assert "role=?" in line
    assert "backend=none" in line
