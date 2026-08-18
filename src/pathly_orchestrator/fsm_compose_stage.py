"""Per-stage prompt tailoring: section drops, stage overrides, adapter choice."""

from __future__ import annotations


def _drop_sections(text: str, excluded: set[str]) -> str:
    """Drop ``## <heading>`` blocks whose heading is in ``excluded`` (a flow-inspector
    use-once Sections trim). A block runs from its ``## `` line to the next ``## ``/``# ``
    heading or EOF; ``### `` and body lines inside it go too. Only H2 sections are ever
    trimmable — the gate never lists H1 (the skill title) or locked fragment sections for
    exclusion, so this can never drop platform glue (board CRUD / progress / completion).
    """
    if not excluded:
        return text
    out: list[str] = []
    skip = False
    for line in text.split("\n"):
        is_h2 = line.startswith("## ") and not line.startswith("### ")
        is_h1 = line.startswith("# ") and not line.startswith("## ")
        if is_h2:
            skip = line[3:].strip() in excluded
        elif is_h1:
            skip = False  # a new top-level section ends any skipped H2 block
        if not skip:
            out.append(line)
    return "\n".join(out)


def _apply_stage_selection(
    agent_text: str,
    ability_ids: list | None,
    excluded_sections: list | None,
    project_root: str,
) -> str:
    """Apply a per-stage flow-phase-inspector selection to the freshly-composed stage body
    (#5): drop excluded ``##`` sections, then append the selected layer-3 abilities AFTER the
    body — mirroring ``compose_skill_segments(extra_segments=…)`` on the board-run path. Pure
    and guarded (called only when a selection exists), so a stage with none is byte-identical.
    """
    text = agent_text
    if excluded_sections:
        text = _drop_sections(
            text, {s for s in excluded_sections if isinstance(s, str)}
        )
    if ability_ids:
        try:
            from pathly_orchestrator.skills.abilities import ability_segments

            extras = ability_segments(list(ability_ids), project_root or None)
        except Exception:
            extras = []
        bodies = [s.get("text", "") for s in extras if s.get("text")]
        if bodies:
            text = text.rstrip() + "\n\n" + "\n\n".join(bodies)
    return text


def _resolve_adapter(flow_config: dict, state_name: str) -> str:
    adapter_map = flow_config.get("adapter_map") or {}
    return adapter_map.get(state_name) or adapter_map.get("default") or ""
