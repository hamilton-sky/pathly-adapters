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
from .adopt import adopt_untracked_for_host
from .hooks import _apply_hooks  # noqa: F401  (re-exported: tests import it from here)
from .report import report_pruned, report_would_prune
from .skill_catalog import (  # noqa: F401  (DEFAULT_EXPOSED_SKILLS is re-exported)
    DEFAULT_EXPOSED_SKILLS,
    dependents_of,
    load_catalog,
    requires_closure,
    resolve_skill_args,
)

# Must stay in sync with detect_hosts() — any host returned by detect_hosts()
# must appear here, or auto-detected installs will fail with a confusing error.
ALLOWED_HOSTS = {"claude", "codex", "copilot", "antigravity"}

# DEFAULT_EXPOSED_SKILLS (the Tier-1 default set) lives in skill_catalog and is re-exported
# here: the Studio export endpoint and the docs import it from `install_cli.orchestrate`.


def _is_flow(name: str) -> bool:
    """Flow YAMLs share the agents manifest but have their own always-repair sync."""
    return name.endswith(".flow.yaml")


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
    "create-feature": "planning",
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
    "post": "planning",
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


def _select_skill_keys(
    host: str, catalog: dict, export_skills: set[str] | frozenset[str] | None
) -> set[str]:
    """The skill keys to install: the default tier, the requested ``--export`` names, and
    every skill those need (``requires:`` in the skill meta, transitively)."""
    keys, unknown = resolve_skill_args(catalog, sorted(export_skills or ()))
    for name in unknown:
        print(
            f"  [warn] [{host}] unknown skill {name!r} — not exported "
            f"(see `pathly-setup {host} --list`)",
            file=sys.stderr,
        )
    # The default tier is one set for every adapter, but an adapter only has the skills it
    # defines (copilot has no fsm-call) — a default it lacks is simply not installed there.
    chosen = (set(DEFAULT_EXPOSED_SKILLS) & set(catalog)) | set(keys)
    wanted = requires_closure(catalog, chosen)
    pulled = sorted(wanted - chosen)
    if pulled:
        why = ", ".join(
            f"{k} (for {', '.join(dependents_of(catalog, k, wanted))})" for k in pulled
        )
        print(f"[{host}] Also installing required skill(s): {why}")
    return wanted


def _build_skill_files(
    host: str,
    install_cfg: dict,
    dest: Path,
    *,
    export_skills: set[str] | frozenset[str] | None = None,
    all_skills: bool = False,
) -> tuple[Path | None, dict[str, str]]:
    """Stitch the skills to install. Returns ``(skills_dest, {relative path: content})``.

    Tier gate: only the default tier installs, plus whatever ``--export`` names (or
    everything with ``all_skills``). ``(None, {})`` when the host has no skills section.
    """
    skills_cfg = install_cfg.get("skills")
    if not skills_cfg:
        return None, {}
    skills_dest = Path(skills_cfg["destination"]).expanduser()
    catalog = load_catalog(host, nested=skills_cfg.get("structure") == "nested")
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
    wanted = _select_skill_keys(host, catalog, export_skills)

    skill_files: dict[str, str] = {}
    for info in catalog.values():
        if not all_skills and info.key not in wanted:
            continue
        core_file = _grouped_core_file(core_skills_dir, info.key, _SKILL_GROUPS)
        try:
            # Manifest key = core-skills-relative path without ".md" (e.g. "development/build").
            _grp = _SKILL_GROUPS.get(info.key)
            compose_key = f"{_grp}/{info.key}" if _grp else info.key
            skill_files[info.filename] = stitch_skill(
                core_file,
                info.meta_file,
                flows_dest=dest,
                host_instructions=host_instructions,
                compose_key=compose_key,
                adapter=host,
            )
            if host == "codex" and info.filename.endswith("/SKILL.md"):
                skill_dir = info.filename.removesuffix("/SKILL.md")
                skill_files[f"{skill_dir}/agents/openai.yaml"] = (
                    _codex_skill_openai_yaml(info.meta)
                )
        except FileNotFoundError:
            print(
                f"  [warn] No core skill for {info.name!r}, skipping",
                file=sys.stderr,
            )
    return skills_dest, skill_files


def _run_host(
    host: str,
    dry_run: bool,
    repair: bool,
    force: bool,
    *,
    export_skills: frozenset[str] | set[str] | None = None,
    all_skills: bool = False,
) -> None:
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

    skills_dest, skill_files = _build_skill_files(
        host,
        install_cfg,
        dest,
        export_skills=export_skills,
        all_skills=all_skills,
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
        # Removals: --repair prunes every owned file outside the requested set, so the
        # preview has to say what would disappear, not only what would be written.
        report_would_prune(
            host,
            "agent file(s)",
            dest,
            agent_files,
            repair=repair,
            prune_filter=lambda n: not _is_flow(n),
        )
        report_would_prune(
            host,
            "flow(s)",
            dest,
            {f.name: "" for f in core_flows_path().glob("*.flow.yaml")},
            repair=True,  # flows are always reconciled
            prune_filter=_is_flow,
        )
        if skills_dest and skill_files:
            would_adopt = adopt_untracked_for_host(host, install_cfg, dry_run=True)
            report_would_prune(
                host,
                "skill file(s)",
                skills_dest,
                skill_files,
                repair=repair,
                extra_owned=would_adopt,
            )
        if templates_dest and template_files:
            report_would_prune(
                host, "template(s)", templates_dest, template_files, repair=repair
            )
        if plugin_dest and plugin_files:
            report_would_prune(
                host, "plugin file(s)", plugin_dest, plugin_files, repair=repair
            )
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
        # Flow YAMLs live in this manifest too but are reconciled by materialize_flows
        # below — exclude them here so a repair doesn't delete-then-rewrite every flow.
        pruned: list[str] = []
        written = materialize(
            agent_files,
            dest,
            repair=repair,
            force=force,
            dry_run=False,
            prune_filter=lambda n: not _is_flow(n),
            pruned_out=pruned,
        )
        if written:
            written_dests.append(dest)
            print(f"[{host}] Wrote {len(written)} file(s) to {dest}")
        else:
            print(
                f"[{host}] Nothing to write (files already current or not Pathly-owned)"
            )
        report_pruned(host, "agent file(s)", dest, pruned)

        flow_pruned: list[str] = []
        flow_written = materialize_flows(
            dest, force=force, dry_run=False, pruned_out=flow_pruned
        )
        if flow_written:
            if dest not in written_dests:
                written_dests.append(dest)
            print(f"[{host}] Wrote {len(flow_written)} flow(s) to {dest}")
        report_pruned(host, "flow(s)", dest, flow_pruned)

        if skills_dest and skill_files:
            adopt_untracked_for_host(host, install_cfg, dry_run=False)
            pruned = []
            written = materialize(
                skill_files,
                skills_dest,
                repair=repair,
                force=force,
                dry_run=False,
                pruned_out=pruned,
            )
            if written:
                written_dests.append(skills_dest)
                print(f"[{host}] Wrote {len(written)} skill(s) to {skills_dest}")
            report_pruned(host, "skill file(s)", skills_dest, pruned)

        if templates_dest and template_files:
            pruned = []
            written = materialize(
                template_files,
                templates_dest,
                repair=repair,
                force=force,
                dry_run=False,
                pruned_out=pruned,
            )
            if written:
                written_dests.append(templates_dest)
                print(f"[{host}] Wrote {len(written)} template(s) to {templates_dest}")
            report_pruned(host, "template(s)", templates_dest, pruned)

        if plugin_dest and plugin_files:
            pruned = []
            written = materialize(
                plugin_files,
                plugin_dest,
                repair=repair,
                force=force,
                dry_run=False,
                pruned_out=pruned,
            )
            report_pruned(host, "plugin file(s)", plugin_dest, pruned)
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
        # untracked Pathly skills (manifest lost them) are adopted so they go too
        adopted = adopt_untracked_for_host(host, install_cfg, dry_run=dry_run)
        skill_removed = uninstall(skills_dest, dry_run=dry_run)
        if dry_run:
            skill_removed = sorted(set(skill_removed) | set(adopted))
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
