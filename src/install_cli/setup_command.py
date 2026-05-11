import argparse
import importlib.metadata
import subprocess
import sys
from pathlib import Path

import yaml

from .detect import detect_hosts
from .mcp_config import install_mcp_config, uninstall_mcp_config
from .resources import adapter_meta_path, adapter_install_yaml, core_agents_path, core_skills_path
from .stitch import stitch_agent, stitch_skill
from .materialize import materialize, uninstall

_TELEMETRY_FOOTER = """
---

*Telemetry: when your task is complete, call the `record_activity` MCP tool with \
your agent name, the feature you worked on, and a one-line summary of what you did. \
Pass `input_tokens` and `output_tokens` if you have estimates (or leave them as 0).*
""".strip()


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
        core_file = core_dir / f"{agent_name}.md"
        if not core_file.exists():
            print(f"  [warn] No core file for {agent_name!r}, skipping", file=sys.stderr)
            continue
        agent_files[f"{agent_name}.md"] = stitch_agent(core_file, meta_file, footer=footer)

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
                skill_files[skill_meta.get("filename", default_filename)] = stitch_skill(core_file, meta_file)
            except FileNotFoundError:
                print(f"  [warn] No core skill for {skill_name!r}, skipping", file=sys.stderr)

    if dry_run:
        print(f"\n[{host}] Would write to {dest}:")
        for name in sorted(agent_files):
            print(f"  {dest / name}")
        if skills_dest and skill_files:
            print(f"\n[{host}] Would write skills to {skills_dest}:")
            for name in sorted(skill_files):
                print(f"  {skills_dest / name}")
        if telemetry_enabled:
            install_mcp_config(host, dry_run=True)
        return

    written_dests: list[Path] = []
    mcp_registered = False
    try:
        written = materialize(agent_files, dest, repair=repair, force=force, dry_run=False)
        if written:
            written_dests.append(dest)
            print(f"[{host}] Wrote {len(written)} file(s) to {dest}")
        else:
            print(f"[{host}] Nothing to write (files already current or not Pathly-owned)")

        if skills_dest and skill_files:
            written = materialize(skill_files, skills_dest, repair=repair, force=force, dry_run=False)
            if written:
                written_dests.append(skills_dest)
                print(f"[{host}] Wrote {len(written)} skill(s) to {skills_dest}")

        if telemetry_enabled:
            install_mcp_config(host, dry_run=False)
            mcp_registered = True

    except Exception:
        print(f"[{host}] Install failed — rolling back.", file=sys.stderr)
        for d in written_dests:
            try:
                uninstall(d)
            except Exception:
                pass
        if mcp_registered:
            try:
                uninstall_mcp_config(host, dry_run=False)
            except Exception:
                pass
        raise


def _run_host_uninstall(host: str, dry_run: bool) -> None:
    install_cfg = _load_install_yaml(host)
    dest = Path(install_cfg["destination"]).expanduser()

    if install_cfg.get("telemetry"):
        uninstall_mcp_config(host, dry_run=dry_run)

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
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("pathly-adapters removed. Goodbye!")
    else:
        print("Package removal failed — run manually:", " ".join(cmd), file=sys.stderr)
