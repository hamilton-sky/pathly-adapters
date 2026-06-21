from pathlib import Path

_PROMPT_ROOTS = [
    Path(__file__).parent.parent / "src/pathly_data/core/skills",
    Path(__file__).parent.parent / "src/pathly_data/core/agents",
]


def test_prompt_json_event_examples_include_timestamps() -> None:
    failures: list[str] = []

    for root in _PROMPT_ROOTS:
        for path in root.rglob("*.md"):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if '{"type"' not in line or '"ts"' in line:
                    continue
                failures.append(
                    f"{path.relative_to(root.parent.parent)}:{line_number}: {line.strip()}"
                )

    assert not failures, (
        "Prompt JSON event examples must include a timestamp so EVENTS.jsonl "
        "entries remain renderable in Studio:\n" + "\n".join(failures)
    )
