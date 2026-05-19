import argparse
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import yaml

from .codex_plugin_config import install_codex_plugin, uninstall_codex_plugin
from .detect import detect_hosts
from .resources import adapter_meta_path, adapter_path, adapter_install_yaml, core_agents_path, core_flows_path, core_skills_path, core_templates_path
from .stitch import stitch_agent, stitch_skill
from .materialize import (
    materialize,
    materialize_flows,
    uninstall,
)

# Must stay in sync with detect_hosts() — any host returned by detect_hosts()
# must appear here, or auto-detected installs will fail with a confusing error.
ALLOWED_HOSTS = {"claude", "codex", "copilot"}

_TELEMETRY_FOOTER = """
---

*Telemetry: when your task is complete, run:*
```bash
curl -s -X POST http://127.0.0.1:8765/record_activity \
  -H "Content-Type: application/json" \
  -d '{"agent":"<your-agent-name>","feature":"<feature>","summary":"<one-line summary>","input_tokens":0,"output_tokens":0}'
```
""".strip()


def _codex_skill_openai_yaml(skill_meta: dict) -> str:
    display_name = skill_meta.get("display_name") or f"Pathly {skill_meta['skill']}"
    short_description = (
        skill_meta.get("short_description")
        or skill_meta.get("natural_language")
        or f"Run the Pathly {skill_meta['skill']} workflow."
    )
    default_prompt = skill_meta.get("default_prompt") or f"Use Pathly {skill_meta['skill']}"
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
            core_file = core_dir / f"{agent_name}.md"
        if not core_file.exists():
            print(f"  [warn] No core file for {agent_name!r}, skipping", file=sys.stderr)
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
        for meta_file in sorted(meta_dir.glob("*_skill.yaml")):
            skill_name = meta_file.stem.removesuffix("_skill")
            skill_meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
            core_file = core_skills_dir / f"{skill_meta['skill']}.md"
            default_filename = f"{skill_name}/SKILL.md" if nested else f"{skill_name}.md"
            try:
                filename = skill_meta.get("filename", default_filename)
                skill_files[filename] = stitch_skill(core_file, meta_file, flows_dest=dest)
                if host == "codex" and filename.endswith("/SKILL.md"):
                    skill_dir = filename.removesuffix("/SKILL.md")
                    skill_files[f"{skill_dir}/agents/openai.yaml"] = _codex_skill_openai_yaml(skill_meta)
            except FileNotFoundError:
                print(f"  [warn] No core skill for {skill_name!r}, skipping", file=sys.stderr)

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
            raise FileNotFoundError(f"No plugin source for host {host!r}: {plugin_root}")
        for plugin_file in sorted(plugin_root.rglob("*")):
            if plugin_file.is_file():
                rel = plugin_file.relative_to(plugin_root).as_posix()
                plugin_files[f"{source_name}/{rel}"] = plugin_file.read_text(encoding="utf-8")
        if plugin_cfg.get("include_stitched"):
            for name, content in agent_files.items():
                plugin_files[f"agents/{name}"] = content
            for flow_file in sorted(core_flows_path().glob("*.flow.yaml")):
                plugin_files[f"flows/{flow_file.name}"] = flow_file.read_text(encoding="utf-8")
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
        return

    written_dests: list[Path] = []
    codex_plugin_registered = False
    try:
        written = materialize(agent_files, dest, repair=repair, force=force, dry_run=False)
        if written:
            written_dests.append(dest)
            print(f"[{host}] Wrote {len(written)} file(s) to {dest}")
        else:
            print(f"[{host}] Nothing to write (files already current or not Pathly-owned)")

        flow_written = materialize_flows(dest, repair=repair, force=force, dry_run=False)
        if flow_written:
            if dest not in written_dests:
                written_dests.append(dest)
            print(f"[{host}] Wrote {len(flow_written)} flow(s) to {dest}")

        if skills_dest and skill_files:
            written = materialize(skill_files, skills_dest, repair=repair, force=force, dry_run=False)
            if written:
                written_dests.append(skills_dest)
                print(f"[{host}] Wrote {len(written)} skill(s) to {skills_dest}")

        if templates_dest and template_files:
            written = materialize(template_files, templates_dest, repair=repair, force=force, dry_run=False)
            if written:
                written_dests.append(templates_dest)
                print(f"[{host}] Wrote {len(written)} template(s) to {templates_dest}")

        if plugin_dest and plugin_files:
            written = materialize(plugin_files, plugin_dest, repair=repair, force=force, dry_run=False)
            if written:
                written_dests.append(plugin_dest)
                print(f"[{host}] Wrote {len(written)} plugin file(s) to {plugin_dest}")

        if host == "codex" and plugin_files:
            install_codex_plugin(plugin_files, dry_run=False)
            codex_plugin_registered = True

    except Exception:
        print(f"[{host}] Install failed — rolling back.", file=sys.stderr)
        for d in written_dests:
            try:
                uninstall(d)
            except Exception:
                pass
        if codex_plugin_registered:
            try:
                uninstall_codex_plugin(dry_run=False)
            except Exception:
                pass
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
            print(f"\n[{host}] Would remove {len(skill_removed)} skill(s) from {skills_dest}:")
            for name in sorted(skill_removed):
                print(f"  {skills_dest / name}")
        elif skill_removed:
            print(f"[{host}] Removed {len(skill_removed)} skill(s) from {skills_dest}")

    templates_cfg = install_cfg.get("templates")
    if templates_cfg:
        templates_dest = Path(templates_cfg["destination"]).expanduser()
        tmpl_removed = uninstall(templates_dest, dry_run=dry_run)
        if dry_run:
            print(f"\n[{host}] Would remove {len(tmpl_removed)} template(s) from {templates_dest}:")
            for name in sorted(tmpl_removed):
                print(f"  {templates_dest / name}")
        elif tmpl_removed:
            print(f"[{host}] Removed {len(tmpl_removed)} template(s) from {templates_dest}")

    plugin_cfg = install_cfg.get("plugin")
    if plugin_cfg:
        plugin_dest = Path(plugin_cfg["destination"]).expanduser()
        plugin_removed = uninstall(plugin_dest, dry_run=dry_run)
        if dry_run:
            print(f"\n[{host}] Would remove {len(plugin_removed)} plugin file(s) from {plugin_dest}:")
            for name in sorted(plugin_removed):
                print(f"  {plugin_dest / name}")
        elif plugin_removed:
            print(f"[{host}] Removed {len(plugin_removed)} plugin file(s) from {plugin_dest}")


def main() -> None:
    try:
        _version = importlib.metadata.version("pathly-adapters")
    except importlib.metadata.PackageNotFoundError:
        _version = "dev"

    parser = argparse.ArgumentParser(
        prog="pathly-setup",
        description="Stitch and install Pathly agent files into AI host tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version}")
    parser.add_argument(
        "host", nargs="?",
        help="Target host (claude, codex, copilot). Defaults to all detected.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview writes without touching the filesystem.")
    parser.add_argument("--apply", action="store_true", help="Write agent files to host config locations.")
    parser.add_argument("--repair", action="store_true", help="Overwrite Pathly-owned files.")
    parser.add_argument("--force", action="store_true", help="Overwrite all files, even those not owned by Pathly.")
    parser.add_argument("--uninstall", action="store_true", help="Remove all Pathly-owned files from host config locations.")
    args = parser.parse_args()

    hosts = [args.host] if args.host else detect_hosts()
    for h in hosts:
        if h not in ALLOWED_HOSTS:
            print(f"Error: unsupported host {h!r}. Allowed: {', '.join(sorted(ALLOWED_HOSTS))}", file=sys.stderr)
            sys.exit(1)
    if not hosts:
        print("No supported hosts detected. Install Claude Code, Codex, or VS Code + Copilot first.")
        sys.exit(1)

    if args.uninstall:
        for host in hosts:
            try:
                _run_host_uninstall(host, dry_run=args.dry_run)
            except Exception as e:
                print(f"[{host}] Error: {e}", file=sys.stderr)
        return

    if not args.dry_run and not args.apply:
        _interactive_menu(hosts, repair=args.repair, force=args.force)
        return

    failed = False
    for host in hosts:
        try:
            _run_host(host, dry_run=args.dry_run, repair=args.repair, force=args.force)
        except Exception as e:
            print(f"[{host}] Error: {e}", file=sys.stderr)
            failed = True

    if failed:
        sys.exit(1)


def _interactive_menu(hosts: list[str], *, repair: bool, force: bool) -> None:
    print()
    print("Pathly Setup")
    print("=" * 40)
    print(f"Detected hosts: {', '.join(hosts)}")
    print()
    print("  1. Preview   — show what would be installed")
    print("  2. Install   — deploy agents to all detected hosts")
    print("  3. Uninstall — remove all Pathly-owned files")
    print("  4. Exit")
    print()

    try:
        choice = input("Choice [1-4]: ").strip().strip("﻿")
    except (KeyboardInterrupt, EOFError):
        print()
        return

    if choice == "1":
        print()
        for host in hosts:
            try:
                _run_host(host, dry_run=True, repair=repair, force=force)
            except Exception as e:
                print(f"[{host}] Error: {e}", file=sys.stderr)
        print()
        try:
            confirm = input("Install now? [y/N]: ").strip().strip("﻿").lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if confirm == "y":
            choice = "2"
        else:
            return

    if choice == "2":
        print()
        failed = False
        for host in hosts:
            try:
                _run_host(host, dry_run=False, repair=repair, force=force)
            except Exception as e:
                print(f"[{host}] Error: {e}", file=sys.stderr)
                failed = True
        if failed:
            sys.exit(1)
        print()
        print("Done. Run 'pathly-tokens' to view activity.")

    elif choice == "3":
        print()
        for host in hosts:
            try:
                _run_host_uninstall(host, dry_run=False)
            except Exception as e:
                print(f"[{host}] Error: {e}", file=sys.stderr)
        print()
        try:
            remove_pkg = input("Also remove the pathly-adapters package itself? [y/N]: ").strip().strip("﻿").lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if remove_pkg == "y":
            _uninstall_package()

    elif choice == "4" or choice == "":
        return

    else:
        print(f"Unknown choice: {choice!r}")
        sys.exit(1)


def _uninstall_package() -> None:
    # Prefer pipx if the executable lives inside a pipx venv
    exe = Path(sys.executable)
    use_pipx = "pipx" in str(exe).lower() or "pipx" in str(Path(sys.argv[0])).lower()

    if use_pipx:
        cmd = ["pipx", "uninstall", "pathly-adapters"]
    else:
        cmd = [sys.executable, "-m", "pip", "uninstall", "pathly-adapters", "-y"]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, timeout=60)
    if result.returncode == 0:
        print("pathly-adapters removed. Goodbye!")
    else:
        print("Package removal failed — run manually:", " ".join(cmd), file=sys.stderr)
