"""
Seed flows, skills, and agent definitions from pathly_data into the central DB.
Called by get_db() on first open; no-op if tables are already populated.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """Seed flows, skills, agents from pathly_data if tables are empty."""
    count = conn.execute("SELECT COUNT(*) FROM flow_definitions").fetchone()[0]
    if count > 0:
        return

    import yaml  # type: ignore[import]
    from pathly_orchestrator.db import (
        upsert_agent_definition,
        upsert_flow_definition,
        upsert_skill_definition,
    )

    this_dir = Path(__file__).resolve().parent
    data_root = None
    for parent in [
        this_dir.parent,
        this_dir.parent.parent,
        this_dir.parent.parent.parent,
    ]:
        candidate = parent / "pathly_data" / "core"
        if candidate.exists():
            data_root = parent / "pathly_data"
            break
    if data_root is None:
        log.warning("seed_if_empty: pathly_data not found, skipping seed")
        return

    meta_dir = data_root / "adapters" / "claude" / "_meta"

    # Seed flows
    flows_dir = data_root / "core" / "flows"
    if flows_dir.exists():
        for flow_file in flows_dir.glob("*.flow.yaml"):
            try:
                raw_text = flow_file.read_text(encoding="utf-8")
                flow_data = yaml.safe_load(raw_text)
                name = flow_data.get("flow") or flow_file.stem.replace(".flow", "")
                version = str(flow_data.get("version", "1"))
                upsert_flow_definition(conn, None, name, version, raw_text)
            except Exception as e:
                log.warning(f"seed_if_empty: skipping {flow_file.name}: {e}")

    # Seed agents
    agents_dir = data_root / "core" / "agents"
    if agents_dir.exists():
        for agent_file in agents_dir.rglob("*.md"):
            if "README" in agent_file.name:
                continue
            try:
                role = agent_file.stem
                meta_file = meta_dir / f"{role}.yaml" if meta_dir.exists() else None
                meta: dict = {}
                if meta_file and meta_file.exists():
                    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
                upsert_agent_definition(
                    conn,
                    None,
                    role,
                    name=meta.get("name", role),
                    description=meta.get("description", ""),
                    model=meta.get("model", ""),
                    tools=meta.get("tools", []),
                    can_spawn=meta.get("can_spawn", []),
                )
            except Exception as e:
                log.warning(f"seed_if_empty: skipping agent {agent_file.name}: {e}")

    # Seed skills
    skills_dir = data_root / "core" / "skills"
    if skills_dir.exists():
        for skill_file in skills_dir.rglob("*.md"):
            try:
                skill_name = skill_file.stem
                meta_file = (
                    meta_dir / f"{skill_name}_skill.yaml" if meta_dir.exists() else None
                )
                meta = {}
                if meta_file and meta_file.exists():
                    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
                content = skill_file.read_text(encoding="utf-8")
                upsert_skill_definition(
                    conn,
                    None,
                    skill=meta.get("skill", skill_name),
                    filename=meta.get("filename", skill_file.name),
                    natural_language=meta.get("natural_language", ""),
                    content=content,
                )
            except Exception as e:
                log.warning(f"seed_if_empty: skipping skill {skill_file.name}: {e}")
