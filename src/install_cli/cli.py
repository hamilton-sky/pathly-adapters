import argparse
import importlib.metadata
import subprocess
import sys
from pathlib import Path

from .detect import detect_hosts
from .orchestrate import ALLOWED_HOSTS, _run_host, _run_host_uninstall


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
        "host",
        nargs="?",
        help="Target host (claude, codex, copilot, antigravity). Defaults to all detected.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview writes without touching the filesystem.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write agent files to host config locations.",
    )
    parser.add_argument(
        "--repair", action="store_true", help="Overwrite Pathly-owned files."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite all files, even those not owned by Pathly.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove all Pathly-owned files from host config locations.",
    )
    args = parser.parse_args()

    hosts = [args.host] if args.host else detect_hosts()
    for h in hosts:
        if h not in ALLOWED_HOSTS:
            print(
                f"Error: unsupported host {h!r}. Allowed: {', '.join(sorted(ALLOWED_HOSTS))}",
                file=sys.stderr,
            )
            sys.exit(1)
    if not hosts:
        print(
            "No supported hosts detected. Install Claude Code, Codex, VS Code + Copilot, or Antigravity CLI first."
        )
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
            remove_pkg = (
                input("Also remove the pathly-adapters package itself? [y/N]: ")
                .strip()
                .strip("﻿")
                .lower()
            )
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
