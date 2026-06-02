import re
from pathlib import Path

import yaml


def _compose_or_read(core_path: Path, compose_key: str | None, adapter: str | None) -> str:
    """Return the composed skill body when it's in the composition manifest, else raw.

    A skill absent from the manifest's ``skills:`` map composes to its raw body, so
    this is a behaviour-preserving no-op until that skill is converted.
    """
    raw = core_path.read_text(encoding="utf-8")
    if not compose_key:
        return raw
    try:
        from pathly_orchestrator.compose import compose_skill, load_manifest

        if compose_key in (load_manifest().get("skills") or {}):
            return compose_skill(compose_key, adapter or "claude")
    except Exception:
        # Composition is additive; never let a manifest problem break the installer.
        # (validate_composition is the loud build-time gate; this path stays resilient.)
        return raw
    return raw


def stitch_skill(
    core_path: Path,
    meta_path: Path,
    *,
    flows_dest: Path | None = None,
    host_instructions: str | None = None,
    compose_key: str | None = None,
    adapter: str | None = None,
) -> str:
    with open(meta_path, encoding="utf-8") as f:
        try:
            meta = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Malformed YAML in {meta_path}: {e}") from e

    required = ["skill"]
    missing = [k for k in required if k not in meta]
    if not any(k in meta for k in ("invocation", "natural_language", "wrapper")):
        missing.append("invocation or natural_language")
    if missing:
        raise ValueError(f"Missing required fields in {meta_path}: {missing}")

    wrapper = meta.get("wrapper")
    if wrapper is not None:
        body = wrapper
    else:
        if not core_path.exists():
            raise FileNotFoundError(f"Core skill file not found: {core_path}")
        body = _compose_or_read(core_path, compose_key, adapter)

    if meta.get("strip_frontmatter"):
        body = re.sub(r"^---\n.*?\n---\n", "", body, count=1, flags=re.DOTALL)

    for key, val in meta.get("variables", {}).items():
        body = body.replace("{{" + key + "}}", str(val))

    if flows_dest is not None:
        body = body.replace("src/pathly_data/core/flows/", flows_dest.as_posix() + "/")

    # Prepend YAML frontmatter — required by hosts like Codex that identify skills
    # by reading the frontmatter block at the top of the skill file.
    description = (
        meta.get("description")
        or meta.get("natural_language")
        or meta.get("invocation")
        or ""
    )
    frontmatter: dict = {"name": meta["skill"], "description": description}
    fm_str = yaml.dump(
        frontmatter, default_flow_style=False, allow_unicode=True
    ).strip()
    parts = [f"---\n{fm_str}\n---"]
    if host_instructions:
        parts.append(host_instructions.strip())
    parts.append(body)
    body = "\n\n".join(parts)

    return body


def stitch_agent(core_path: Path, meta_path: Path, *, footer: str | None = None) -> str:
    if not core_path.exists():
        raise FileNotFoundError(f"Core agent file not found: {core_path}")

    with open(meta_path, encoding="utf-8") as f:
        try:
            meta = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Malformed YAML in {meta_path}: {e}") from e

    required = ["name", "description", "model"]
    missing = [k for k in required if k not in meta]
    if missing:
        raise ValueError(f"Missing required fields in {meta_path}: {missing}")

    core_body = core_path.read_text(encoding="utf-8").strip()

    frontmatter: dict = {
        "name": meta["name"],
        "description": meta["description"],
        "model": meta["model"],
    }
    if meta.get("tools"):
        frontmatter["tools"] = meta["tools"]
    if meta.get("can_spawn"):
        frontmatter["can_spawn"] = meta["can_spawn"]

    fm_str = yaml.dump(
        frontmatter, default_flow_style=False, allow_unicode=True
    ).strip()

    parts = [f"---\n{fm_str}\n---", core_body]

    if meta.get("spawn_section"):
        parts.append(meta["spawn_section"].strip())

    if footer:
        parts.append(footer.strip())

    return "\n\n".join(parts) + "\n"
