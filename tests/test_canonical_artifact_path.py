from pathly_orchestrator.db.queries.comms_artifacts import canonical_artifact_path


def test_windows_absolute_path():
    result = canonical_artifact_path(r"C:\Users\x\pathly\features\f\SPEC.md")
    assert result == "pathly/features/f/SPEC.md"


def test_posix_absolute_path():
    result = canonical_artifact_path("/home/u/pathly/plans/f/A.md")
    assert result == "pathly/plans/f/A.md"


def test_relative_path_passthrough():
    result = canonical_artifact_path("pathly/features/f/B.md")
    assert result == "pathly/features/f/B.md"


def test_no_pathly_segment_passthrough():
    result = canonical_artifact_path("foo/bar.md")
    assert result == "foo/bar.md"
