import re
from pathlib import Path

import yaml


def stitch_skill(core_path: Path, meta_path: Path) -> str:
    with open(meta_path, encoding="utf-8") as f:
        try:
            meta = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Malformed YAML in {meta_path}: {e}") from e

    required = ["skill", "invocation"]
    missing = [k for k in required if k not in meta]
    if missing:
        raise ValueError(f"Missing required fields in {meta_path}: {missing}")

    wrapper = meta.get("wrapper")
    if wrapper is not None:
        body = wrapper
    else:
        if not core_path.exists():
            raise FileNotFoundError(f"Core skill file not found: {core_path}")
        body = core_path.read_text(encoding="utf-8")

    if meta.get("strip_frontmatter"):
        body = re.sub(r"^---\n.*?\n---\n", "", body, count=1, flags=re.DOTALL)

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

    fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).strip()

    parts = [f"---\n{fm_str}\n---", core_body]

    if meta.get("spawn_section"):
        parts.append(meta["spawn_section"].strip())

    if footer:
        parts.append(footer.strip())

    return "\n\n".join(parts) + "\n"
