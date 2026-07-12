import json
import sys
from pathlib import Path

import yaml

from .codex_plugin_config import install_codex_plugin, uninstall_codex_plugin
from .resources import (
    adapter_meta_path,
    adapter_path,
    adapter_install_yaml,
    core_agents_path,
    core_flows_path,
    core_skills_path,
    core_templates_path,
)
from .stitch import stitch_agent, stitch_skill
from .materialize import (
    materialize,
    materialize_flows,
    uninstall,
)

# Must stay in sync with detect_hosts() — any host returned by detect_hosts()
# must appear here, or auto-detected installs will fail with a confusing error.
ALLOWED_HOSTS = {"claude", "codex", "copilot", "antigravity"}

# Substring that identifies a hook command as Pathly-owned.
_PATHLY_HOOK_MARKER = "pathly_hooks"


def _apply_hooks(host: str, hooks_cfg: dict, *, dry_run: bool, repair: bool) -> None:
    """Merge Pathly hooks into the host's settings.json.

    Hook entries whose command contains 'pathly_hooks' are treated as
    Pathly-owned.  In normal mode they are left as-is; repair=True replaces
    them with the canonical commands from hooks_cfg.

    All other settings in settings.json are preserved unchanged.
    """
    settings_dest_str = hooks_cfg.get("settings_dest")
    if not settings_dest_str:
        return
    settings_path = Path(settings_dest_str).expanduser()

    # event → [cmd, ...] (skip the settings_dest metadata key)
    events: dict[str, list[str]] = {
        k: ([v] if isinstance(v, str) else list(v))
        for k, v in hooks_cfg.items()
        if k != "settings_dest"
    }
    if not events:
        return

    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {}

    existing_hooks: dict = settings.get("hooks", {})
    changed = False

    for event, commands in events.items():
        event_groups: list = list(existing_hooks.get(event, []))

        pathly_indices = [
            i
            for i, g in enumerate(event_groups)
            if isinstance(g, dict)
            and any(
                _PATHLY_HOOK_MARKER in h.get("command", "")
                for h in g.get("hooks", [])
                if isinstance(h, dict)
            )
        ]

        new_group: dict = {
            "hooks": [{"type": "command", "command": cmd} for cmd in commands]
        }

        if not pathly_indices:
            event_groups.append(new_group)
            changed = True
        elif repair:
            kept = [
                g for i, g in enumerate(event_groups) if i not in set(pathly_indices)
            ]
            kept.append(new_group)
            event_groups = kept
            changed = True
        # else: existing Pathly hooks, repair not requested — leave as-is

        existing_hooks[event] = event_groups

    if not changed:
        return

    settings["hooks"] = existing_hooks

    if dry_run:
        print(f"[{host}] Would update hooks in {settings_path}")
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"[{host}] Updated hooks in {settings_path}")


def _run_mcp(host: str, mcp_cfg: dict, *, dry_run: bool, repair: bool) -> None:
    """Deep-merge each adapters/<host>/_mcp/*.json into the host's MCP config.

    Each template is ``{"mcpServers": {"<name>": {...}}}``. Servers from the
    templates are Pathly-owned: added when absent, overwritten on ``repair=True``;
    all other (pre-existing) servers in the host config are preserved. The
    destination comes from the adapter's ``install.yaml`` ``mcp.destination``.
    Because it globs ``_mcp/*.json``, dropping more templates (e.g. serena.json)
    alongside codebase-memory-mcp.json merges them all in one run — no code change needed.
    """
    dest_str = mcp_cfg.get("destination")
    if not dest_str:
        return
    mcp_dir = adapter_path(host) / "_mcp"
    templates = sorted(mcp_dir.glob("*.json")) if mcp_dir.is_dir() else []
    incoming: dict[str, dict] = {}
    for tf in templates:
        try:
            data = json.loads(tf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for name, spec in (data.get("mcpServers") or {}).items():
            incoming[name] = spec
    if not incoming:
        return

    dest_path = Path(dest_str).expanduser()
    config: dict = {}
    if dest_path.exists():
        try:
            config = json.loads(dest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}
    servers: dict = dict(config.get("mcpServers") or {})

    changed = False
    for name, spec in incoming.items():
        if name not in servers or repair:
            servers[name] = spec
            changed = True
    if not changed:
        return
    config["mcpServers"] = servers

    if dry_run:
        print(f"[{host}] Would merge {len(incoming)} MCP server(s) into {dest_path}")
        return
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[{host}] Merged {len(incoming)} MCP server(s) into {dest_path}")


_AGENT_GROUPS = {
    "architect": "planning",
    "builder": "building",
    "designer": "building",
    "evaluator": "research",
    "explorer": "research",
    "orchestrator": "support",
    "planner": "planning",
    "po": "planning",
    "quick": "support",
    "reviewer": "quality",
    "scout": "research",
    "tester": "quality",
    "web-researcher": "research",
}

_SKILL_GROUPS = {
    "archive-artifacts": "utilities",
    "archive": "utilities",
    "back": "controls",
    "build": "development",
    "commit": "development",
    "dag-sketch": "planning",
    "debug": "development",
    "design": "development",
    "dispatch": "utilities",
    "end": "controls",
    "explore": "development",
    "ff": "controls",
    "fix": "development",
    "quick-fix": "development",
    "fsm-call": "utilities",
    "go": "controls",
    "goalize": "planning",
    "help": "utilities",
    "lessons": "utilities",
    "log-agent-done": "utilities",
    "log": "utilities",
    "meet": "utilities",
    "pathly": "controls",
    "pause": "controls",
    "plan": "planning",
    "po": "planning",
    "prd-import": "planning",
    "retro": "planning",
    "reflect": "utilities",
    "review": "development",
    "scout-path": "utilities",
    "start": "controls",
    "status": "controls",
    "storm": "planning",
    "team": "team",
    "test": "development",
    "verify-state": "utilities",
}

_TELEMETRY_FOOTER = """
---

*Telemetry: when your task is complete, run:*
```bash
pathly-fsm-call record-activity \
  --agent "<your-agent-name>" \
  --feature "<feature>" \
  --summary "<one-line summary>" \
  --input-tokens 0 \
  --output-tokens 0
```
""".strip()


def _grouped_core_file(root: Path, name: str, groups: dict[str, str]) -> Path:
    group = groups.get(name)
    return root / group / f"{name}.md" if group else root / f"{name}.md"


def _codex_skill_openai_yaml(skill_meta: dict) -> str:
    display_name = skill_meta.get("display_name") or f"Pathly {skill_meta['skill']}"
    short_description = (
        skill_meta.get("short_description")
        or skill_meta.get("natural_language")
        or f"Run the Pathly {skill_meta['skill']} workflow."
    )
    default_prompt = (
        skill_meta.get("default_prompt") or f"Use Pathly {skill_meta['skill']}"
    )
    return yaml.safe_dump(
        {
            "interface": {
                "display_name": display_name,
                "short_description": short_description,
                "default_prompt": default_prompt,
            }
        },
        sort_keys=False,
        allow_unicode=True,
    )


def _toml_string(value: object) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def _codex_agent_toml(agent_meta: dict, instructions: str) -> str:
    lines = [
        f"name = {_toml_string(agent_meta.get('name'))}",
        f"description = {_toml_string(agent_meta.get('description'))}",
    ]
    if agent_meta.get("model"):
        lines.append(f"model = {_toml_string(agent_meta.get('model'))}")
    lines.append(f"developer_instructions = {_toml_string(instructions)}")
    return "\n".join(lines) + "\n"


def _load_install_yaml(host: str) -> dict:
    install_path = adapter_install_yaml(host)
    if not install_path.exists():
        raise FileNotFoundError(f"No install.yaml for host {host!r}: {install_path}")
    with open(install_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _run_host(host: str, dry_run: bool, repair: bool, force: bool) -> None:
    install_cfg = _load_install_yaml(host)
    dest = Path(install_cfg["destination"]).expanduser()

    meta_dir = adapter_meta_path(host)
    core_dir = core_agents_path()

    telemetry_enabled = install_cfg.get("telemetry", False)
    footer = _TELEMETRY_FOOTER if telemetry_enabled else None

    agent_files: dict[str, str] = {}
    for meta_file in sorted(meta_dir.glob("*.yaml")):
        if meta_file.name == "install.yaml":
            continue
        if meta_file.stem.endswith("_skill"):
            continue
        agent_name = meta_file.stem
        agent_meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
        if "core_file" in agent_meta:
            core_file = core_dir.parent / agent_meta["core_file"]
        else:
            core_file = _grouped_core_file(core_dir, agent_name, _AGENT_GROUPS)
        if not core_file.exists():
            print(
                f"  [warn] No core file for {agent_name!r}, skipping", file=sys.stderr
            )
            continue
        stitched = stitch_agent(core_file, meta_file, footer=footer)
        if host == "codex":
            default_toml = f"{agent_name}.toml"
            toml_stem = agent_meta.get("filename", default_toml)
            if not toml_stem.endswith(".toml"):
                toml_stem = toml_stem.removesuffix(".md") + ".toml"
            agent_files[toml_stem] = _codex_agent_toml(agent_meta, stitched)
        else:
            filename = agent_meta.get("filename", f"{agent_name}.md")
            agent_files[filename] = stitched

    skills_cfg = install_cfg.get("skills")
    skill_files: dict[str, str] = {}
    skills_dest: Path | None = None
    if skills_cfg:
        skills_dest = Path(skills_cfg["destination"]).expanduser()
        nested = skills_cfg.get("structure") == "nested"
        core_skills_dir = core_skills_path()
        host_instructions: str | None = None
        instructions_name = skills_cfg.get("host_instructions")
        if instructions_name:
            instructions_path = adapter_path(host) / instructions_name
            if not instructions_path.exists():
                raise FileNotFoundError(
                    f"No skill host instructions for {host!r}: {instructions_path}"
                )
            host_instructions = instructions_path.read_text(encoding="utf-8")
        for meta_file in sorted(meta_dir.glob("*_skill.yaml")):
            skill_name = meta_file.stem.removesuffix("_skill")
            skill_meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
            core_file = _grouped_core_file(
                core_skills_dir, skill_meta["skill"], _SKILL_GROUPS
            )
            default_filename = (
                f"{skill_name}/SKILL.md" if nested else f"{skill_name}.md"
            )
            try:
                filename = skill_meta.get("filename", default_filename)
                # Manifest key = core-skills-relative path without ".md" (e.g. "development/build").
                _grp = _SKILL_GROUPS.get(skill_meta["skill"])
                compose_key = (
                    f"{_grp}/{skill_meta['skill']}" if _grp else skill_meta["skill"]
                )
                skill_files[filename] = stitch_skill(
                    core_file,
                    meta_file,
                    flows_dest=dest,
                    host_instructions=host_instructions,
                    compose_key=compose_key,
                    adapter=host,
                )
                if host == "codex" and filename.endswith("/SKILL.md"):
                    skill_dir = filename.removesuffix("/SKILL.md")
                    skill_files[f"{skill_dir}/agents/openai.yaml"] = (
                        _codex_skill_openai_yaml(skill_meta)
                    )
            except FileNotFoundError:
                print(
                    f"  [warn] No core skill for {skill_name!r}, skipping",
                    file=sys.stderr,
                )

    templates_cfg = install_cfg.get("templates")
    template_files: dict[str, str] = {}
    templates_dest: Path | None = None
    if templates_cfg:
        templates_dest = Path(templates_cfg["destination"]).expanduser()
        tmpl_root = core_templates_path()
        for tmpl_file in sorted(tmpl_root.rglob("*.md")):
            rel = tmpl_file.relative_to(tmpl_root).as_posix()
            template_files[rel] = tmpl_file.read_text(encoding="utf-8")

    plugin_cfg = install_cfg.get("plugin")
    plugin_files: dict[str, str] = {}
    plugin_dest: Path | None = None
    if plugin_cfg:
        plugin_dest = Path(plugin_cfg["destination"]).expanduser()
        source_name = plugin_cfg["source"].rstrip("/")
        plugin_root = adapter_path(host) / source_name
        if not plugin_root.exists():
            raise FileNotFoundError(
                f"No plugin source for host {host!r}: {plugin_root}"
            )
        for plugin_file in sorted(plugin_root.rglob("*")):
            if plugin_file.is_file():
                rel = plugin_file.relative_to(plugin_root).as_posix()
                plugin_files[f"{source_name}/{rel}"] = plugin_file.read_text(
                    encoding="utf-8"
                )
        if plugin_cfg.get("include_stitched"):
            for name, content in agent_files.items():
                plugin_files[f"agents/{name}"] = content
            for flow_file in sorted(core_flows_path().glob("*.flow.yaml")):
                plugin_files[f"flows/{flow_file.name}"] = flow_file.read_text(
                    encoding="utf-8"
                )
            for name, content in skill_files.items():
                plugin_files[f"skills/{name}"] = content
            for name, content in template_files.items():
                plugin_files[f"templates/{name}"] = content

    if dry_run:
        print(f"\n[{host}] Would write to {dest}:")
        for name in sorted(agent_files):
            print(f"  {dest / name}")
        for name in sorted(f.name for f in core_flows_path().glob("*.flow.yaml")):
            print(f"  {dest / name}")
        if skills_dest and skill_files:
            print(f"\n[{host}] Would write skills to {skills_dest}:")
            for name in sorted(skill_files):
                print(f"  {skills_dest / name}")
        if templates_dest and template_files:
            print(f"\n[{host}] Would write templates to {templates_dest}:")
            for name in sorted(template_files):
                print(f"  {templates_dest / name}")
        if plugin_dest and plugin_files:
            print(f"\n[{host}] Would write plugin files to {plugin_dest}:")
            for name in sorted(plugin_files):
                print(f"  {plugin_dest / name}")
        if host == "codex" and plugin_files:
            install_codex_plugin(plugin_files, dry_run=True)
        hooks_cfg = install_cfg.get("hooks", {})
        if hooks_cfg:
            _apply_hooks(host, hooks_cfg, dry_run=True, repair=repair)
        mcp_cfg = install_cfg.get("mcp", {})
        if mcp_cfg:
            _run_mcp(host, mcp_cfg, dry_run=True, repair=repair)
        return

    written_dests: list[Path] = []
    codex_plugin_registered = False
    try:
        written = materialize(
            agent_files, dest, repair=repair, force=force, dry_run=False
        )
        if written:
            written_dests.append(dest)
            print(f"[{host}] Wrote {len(written)} file(s) to {dest}")
        else:
            print(
                f"[{host}] Nothing to write (files already current or not Pathly-owned)"
            )

        flow_written = materialize_flows(dest, force=force, dry_run=False)
        if flow_written:
            if dest not in written_dests:
                written_dests.append(dest)
            print(f"[{host}] Wrote {len(flow_written)} flow(s) to {dest}")

        if skills_dest and skill_files:
            written = materialize(
                skill_files, skills_dest, repair=repair, force=force, dry_run=False
            )
            if written:
                written_dests.append(skills_dest)
                print(f"[{host}] Wrote {len(written)} skill(s) to {skills_dest}")

        if templates_dest and template_files:
            written = materialize(
                template_files,
                templates_dest,
                repair=repair,
                force=force,
                dry_run=False,
            )
            if written:
                written_dests.append(templates_dest)
                print(f"[{host}] Wrote {len(written)} template(s) to {templates_dest}")

        if plugin_dest and plugin_files:
            written = materialize(
                plugin_files, plugin_dest, repair=repair, force=force, dry_run=False
            )
            if written:
                written_dests.append(plugin_dest)
                print(f"[{host}] Wrote {len(written)} plugin file(s) to {plugin_dest}")

        if host == "codex" and plugin_files:
            install_codex_plugin(plugin_files, dry_run=False)
            codex_plugin_registered = True

        hooks_cfg = install_cfg.get("hooks", {})
        if hooks_cfg:
            _apply_hooks(host, hooks_cfg, dry_run=False, repair=repair)

        mcp_cfg = install_cfg.get("mcp", {})
        if mcp_cfg:
            _run_mcp(host, mcp_cfg, dry_run=False, repair=repair)

    except Exception:
        print(f"[{host}] Install failed — rolling back.", file=sys.stderr)
        for d in written_dests:
            try:
                uninstall(d)
            except Exception as e:
                print(f"[pathly rollback error] {e}", file=sys.stderr)
        if codex_plugin_registered:
            try:
                uninstall_codex_plugin(dry_run=False)
            except Exception as e:
                print(f"[pathly rollback error] {e}", file=sys.stderr)
        raise


def _run_host_uninstall(host: str, dry_run: bool) -> None:
    install_cfg = _load_install_yaml(host)
    dest = Path(install_cfg["destination"]).expanduser()

    if host == "codex":
        uninstall_codex_plugin(dry_run=dry_run)

    removed = uninstall(dest, dry_run=dry_run)
    if dry_run:
        print(f"\n[{host}] Would remove {len(removed)} file(s) from {dest}:")
        for name in sorted(removed):
            print(f"  {dest / name}")
    elif removed:
        print(f"[{host}] Removed {len(removed)} file(s) from {dest}")
    else:
        print(f"[{host}] Nothing to remove.")

    skills_cfg = install_cfg.get("skills")
    if skills_cfg:
        skills_dest = Path(skills_cfg["destination"]).expanduser()
        skill_removed = uninstall(skills_dest, dry_run=dry_run)
        if dry_run:
            print(
                f"\n[{host}] Would remove {len(skill_removed)} skill(s) from {skills_dest}:"
            )
            for name in sorted(skill_removed):
                print(f"  {skills_dest / name}")
        elif skill_removed:
            print(f"[{host}] Removed {len(skill_removed)} skill(s) from {skills_dest}")

    templates_cfg = install_cfg.get("templates")
    if templates_cfg:
        templates_dest = Path(templates_cfg["destination"]).expanduser()
        tmpl_removed = uninstall(templates_dest, dry_run=dry_run)
        if dry_run:
            print(
                f"\n[{host}] Would remove {len(tmpl_removed)} template(s) from {templates_dest}:"
            )
            for name in sorted(tmpl_removed):
                print(f"  {templates_dest / name}")
        elif tmpl_removed:
            print(
                f"[{host}] Removed {len(tmpl_removed)} template(s) from {templates_dest}"
            )

    plugin_cfg = install_cfg.get("plugin")
    if plugin_cfg:
        plugin_dest = Path(plugin_cfg["destination"]).expanduser()
        plugin_removed = uninstall(plugin_dest, dry_run=dry_run)
        if dry_run:
            print(
                f"\n[{host}] Would remove {len(plugin_removed)} plugin file(s) from {plugin_dest}:"
            )
            for name in sorted(plugin_removed):
                print(f"  {plugin_dest / name}")
        elif plugin_removed:
            print(
                f"[{host}] Removed {len(plugin_removed)} plugin file(s) from {plugin_dest}"
            )
