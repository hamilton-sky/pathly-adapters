"""Round-trip tests for the notebook skill parser/serializer (Phase 0).

Guards the invariants that make the Cells view safe to save Git-tracked files:
  1. Frontmatter is preserved byte-for-byte.
  2. Headings are not doubled (the `## ## Heading` bug).
  3. parse -> serialize is byte-identical for canonically-formatted skill files.
  4. Heading level is preserved (no forced `## `).
"""

from pathly_orchestrator.skills.parser import (
    parse_skill_document,
    serialize_skill_document,
    split_frontmatter,
)


def _round_trip(tmp_path, text: str) -> str:
    f = tmp_path / "skill.md"
    f.write_text(text, encoding="utf-8")
    doc = parse_skill_document(str(f))
    return serialize_skill_document(doc["frontmatter"], doc["body_cells"])


def test_split_frontmatter_extracts_verbatim_block():
    text = "---\nname: build\ndescription: x\n---\nbody here\n"
    fm, body = split_frontmatter(text)
    assert fm == "---\nname: build\ndescription: x\n---\n"
    assert body == "body here\n"


def test_split_frontmatter_absent():
    text = "## Role\n\nNo frontmatter.\n"
    fm, body = split_frontmatter(text)
    assert fm == ""
    assert body == text


def test_round_trip_byte_identical_with_frontmatter(tmp_path):
    text = (
        "---\n"
        "name: build\n"
        "description: build the feature\n"
        "---\n"
        "\n"
        "## Role\n"
        "\n"
        "You are the builder.\n"
        "\n"
        "## Steps\n"
        "\n"
        "Do the thing, then stop.\n"
    )
    assert _round_trip(tmp_path, text) == text


def test_round_trip_byte_identical_no_frontmatter(tmp_path):
    text = (
        "## Role\n"
        "\n"
        "You are the builder.\n"
        "\n"
        "## Steps\n"
        "\n"
        "Do the thing.\n"
    )
    assert _round_trip(tmp_path, text) == text


def test_round_trip_with_preamble(tmp_path):
    text = (
        "---\nname: go\n---\n"
        "\n"
        "Preamble paragraph before any heading.\n"
        "\n"
        "## Section\n"
        "\n"
        "Body.\n"
    )
    assert _round_trip(tmp_path, text) == text


def test_frontmatter_never_dropped(tmp_path):
    text = "---\nname: keep\nmodel: opus\n---\n\n## A\n\nx\n"
    out = _round_trip(tmp_path, text)
    assert out.startswith("---\nname: keep\nmodel: opus\n---\n")


def test_no_doubled_heading_prefix(tmp_path):
    text = "---\nname: x\n---\n\n## What This Delivers\n\nTwo improvements.\n"
    out = _round_trip(tmp_path, text)
    assert "## ## " not in out
    assert "## What This Delivers" in out


def test_parser_returns_bare_heading_and_level(tmp_path):
    f = tmp_path / "skill.md"
    f.write_text("---\nname: x\n---\n\n## Role\n\nbody\n", encoding="utf-8")
    doc = parse_skill_document(str(f))
    cell = doc["body_cells"][0]
    assert cell["heading"] == "Role"  # bare, no '## '
    assert cell["headingLevel"] == 2


def test_serialize_honors_heading_level():
    cells = [{"heading": "Deep", "headingLevel": 3, "content": "x"}]
    assert serialize_skill_document("", cells) == "### Deep\n\nx\n"


def test_serialize_defaults_missing_level_to_two():
    cells = [{"heading": "Plain", "content": "x"}]
    assert serialize_skill_document("", cells) == "## Plain\n\nx\n"
