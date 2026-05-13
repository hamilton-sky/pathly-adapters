import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .resources import hooks_path

MANIFEST_NAME = ".pathly-manifest.json"


def _hook_script_path(name: str) -> Path:
    """Return the absolute path to a pathly_hooks script."""
    return hooks_path() / name


# ---------------------------------------------------------------------------
# Codex hooks
# ---------------------------------------------------------------------------

def deploy_codex_hooks(*, dry_run: bool = False) -> list[str]:
    """Write ~/.codex/hooks.json with Pathly PostToolUse entries.

    Merges into any existing hooks.json — only the 'pathly' key is touched.
    Returns list of paths that were (or would be) written.
    """
    hooks_file = Path.home() / ".codex" / "hooks.json"
    pathly_entries = {
        "classify_feedback": {
            "event": "PostToolUse",
            "matcher": {"tool_name": "apply_patch"},
            "command": str(_hook_script_path("classify_feedback.py")),
        },
        "inject_feedback_ttl": {
            "event": "PostToolUse",
            "matcher": {"tool_name": "apply_patch"},
            "command": str(_hook_script_path("inject_feedback_ttl.py")),
        },
    }

    if dry_run:
        return [str(hooks_file)]

    existing: dict = {}
    if hooks_file.exists():
        try:
            existing = json.loads(hooks_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing["pathly"] = pathly_entries
    hooks_file.parent.mkdir(parents=True, exist_ok=True)
    hooks_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    config_toml = Path.home() / ".codex" / "config.toml"
    if config_toml.exists():
        content = config_toml.read_text(encoding="utf-8")
        if "codex_hooks = true" not in content:
            print(
                "  [note] ~/.codex/config.toml exists but lacks "
                "[features]\\ncodex_hooks = true — hooks may not fire.",
                file=sys.stderr,
            )
    else:
        print(
            "  [note] ~/.codex/config.toml not found — add "
            "[features]\\ncodex_hooks = true to enable hooks.",
            file=sys.stderr,
        )

    return [str(hooks_file)]


def remove_codex_hooks(*, dry_run: bool = False) -> list[str]:
    """Remove the 'pathly' key from ~/.codex/hooks.json.

    Deletes the file if it becomes empty. Returns list of paths affected.
    """
    hooks_file = Path.home() / ".codex" / "hooks.json"
    if not hooks_file.exists():
        return []

    if dry_run:
        return [str(hooks_file)]

    try:
        existing = json.loads(hooks_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    existing.pop("pathly", None)

    if not existing:
        hooks_file.unlink()
    else:
        hooks_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return [str(hooks_file)]


# ---------------------------------------------------------------------------
# Copilot VS Code hooks
# ---------------------------------------------------------------------------

def deploy_copilot_hooks(dest: Path = None, *, dry_run: bool = False) -> list[str]:
    """Write .github/hooks/pathly-classify.json and pathly-ttl.json.

    dest defaults to Path.cwd() / '.github' / 'hooks'.
    Returns list of paths that were (or would be) written.
    """
    if dest is None:
        dest = Path.cwd() / ".github" / "hooks"

    classify_path = dest / "pathly-classify.json"
    ttl_path = dest / "pathly-ttl.json"

    classify_script = _hook_script_path("classify_feedback.py")
    ttl_script = _hook_script_path("inject_feedback_ttl.py")

    classify_content = {
        "event": "PostToolUse",
        "command": {
            "windows": f"python {classify_script} ",
            "linux": f"python3 {classify_script} ",
            "osx": f"python3 {classify_script} ",
        },
    }
    ttl_content = {
        "event": "PostToolUse",
        "command": {
            "windows": f"python {ttl_script} ",
            "linux": f"python3 {ttl_script} ",
            "osx": f"python3 {ttl_script} ",
        },
    }

    if dry_run:
        return [str(classify_path), str(ttl_path)]

    dest.mkdir(parents=True, exist_ok=True)
    classify_path.write_text(json.dumps(classify_content, indent=2), encoding="utf-8")
    ttl_path.write_text(json.dumps(ttl_content, indent=2), encoding="utf-8")

    return [str(classify_path), str(ttl_path)]


def remove_copilot_hooks(dest: Path = None, *, dry_run: bool = False) -> list[str]:
    """Delete Pathly Copilot hook JSON files if they exist.

    Returns list of paths that were (or would be) deleted.
    """
    if dest is None:
        dest = Path.cwd() / ".github" / "hooks"

    targets = [dest / "pathly-classify.json", dest / "pathly-ttl.json"]
    affected = [str(p) for p in targets if p.exists()]

    if dry_run or not affected:
        return affected

    for p in targets:
        try:
            p.unlink()
        except FileNotFoundError:
            pass

    return affected


def _load_manifest(dest: Path) -> dict:
    manifest_path = dest / MANIFEST_NAME
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"files": {}}
    return {"files": {}}


def _save_manifest(dest: Path, manifest: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def materialize(
    files: dict[str, str],
    dest: Path,
    *,
    repair: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Copy stitched agent files to dest. Returns list of filenames written (or would-write)."""
    manifest = _load_manifest(dest)
    owned = set(manifest["files"].keys())
    written: list[str] = []

    for name, content in files.items():
        target = dest / name
        # Guard against path traversal (e.g. name = "../../etc/passwd")
        if not target.resolve().is_relative_to(dest.resolve()):
            raise ValueError(
                f"Path traversal detected: {name!r} escapes destination {dest}"
            )
        if target.exists():
            if name in owned and not repair:
                continue
            if name not in owned and not force:
                continue

        written.append(name)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            manifest["files"][name] = datetime.now(timezone.utc).isoformat()

    if not dry_run and written:
        _save_manifest(dest, manifest)

    return written


def materialize_flows(
    dest: Path,
    *,
    repair: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Copy *.flow.yaml files from the installed package to dest. Returns list of filenames written."""
    from .resources import core_flows_path

    flows_src = core_flows_path()
    files: dict[str, str] = {
        f.name: f.read_text(encoding="utf-8")
        for f in sorted(flows_src.glob("*.flow.yaml"))
    }
    return materialize(files, dest, repair=repair, force=force, dry_run=dry_run)


def uninstall(dest: Path, *, dry_run: bool = False) -> list[str]:
    """Remove all Pathly-owned files from dest using the manifest.

    Returns list of filenames removed (or would-remove in dry_run).
    """
    manifest_path = dest / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"  [warn] No manifest at {manifest_path} — nothing to uninstall.", file=sys.stderr)
        return []

    manifest = _load_manifest(dest)
    removed: list[str] = []

    # Pass 1: validate all entries before touching the filesystem.
    # This prevents partial deletion when a manifest is tampered.
    for name in list(manifest["files"]):
        target = dest / name
        if not target.resolve().is_relative_to(dest.resolve()):
            raise ValueError(
                f"Path traversal detected in manifest: {name!r} escapes destination {dest}"
            )

    # Pass 2: all entries are clean — perform deletions.
    for name in list(manifest["files"]):
        target = dest / name
        removed.append(name)
        if not dry_run:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            # Remove empty parent directories (nested skill dirs)
            try:
                target.parent.rmdir()
            except OSError:
                pass

    if not dry_run:
        try:
            manifest_path.unlink()
        except FileNotFoundError:
            pass

    return removed
