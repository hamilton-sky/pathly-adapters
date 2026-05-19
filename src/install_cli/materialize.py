import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .resources import hooks_path

MANIFEST_NAME = ".pathly-manifest.json"


def _hash_files_dict(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        if "hooks = true" not in content:
            print(
                "  [note] ~/.codex/config.toml exists but lacks "
                "[features]\\nhooks = true — hooks may not fire.",
                file=sys.stderr,
            )
    else:
        print(
            "  [note] ~/.codex/config.toml not found — add "
            "[features]\\nhooks = true to enable hooks.",
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


# ---------------------------------------------------------------------------
# Claude hooks
# ---------------------------------------------------------------------------

def deploy_claude_hooks(*, dry_run: bool = False) -> list[str]:
    """Write ~/.claude/settings.json with Pathly PostToolUse hook entries.

    Merges into any existing settings.json — only the 'hooks.PostToolUse' entry
    is touched (Pathly commands are identified by a comment sentinel in the list).
    Returns list of paths that were (or would be) written.
    """
    settings_file = Path.home() / ".claude" / "settings.json"

    # Forward slashes required: Claude Code runs hooks via sh (Git Bash) on
    # Windows, which consumes backslashes.  Python on Windows accepts / equally.
    classify_cmd = "python " + _hook_script_path("classify_feedback.py").as_posix()
    ttl_cmd      = "python " + _hook_script_path("inject_feedback_ttl.py").as_posix()

    pathly_hook_block = {
        "_pathly": True,
        "hooks": [
            {"type": "command", "command": classify_cmd},
            {"type": "command", "command": ttl_cmd},
        ],
    }

    if dry_run:
        return [str(settings_file)]

    existing: dict = {}
    if settings_file.exists():
        try:
            existing = json.loads(settings_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    hooks: dict = existing.setdefault("hooks", {})
    post_tool_use: list = hooks.setdefault("PostToolUse", [])

    # Remove any stale Pathly entries (keyed by "_pathly" sentinel or old format).
    hooks.pop("classify_feedback", None)
    hooks.pop("inject_feedback_ttl", None)
    post_tool_use[:] = [e for e in post_tool_use if not e.get("_pathly")]

    post_tool_use.append(pathly_hook_block)

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return [str(settings_file)]


def remove_claude_hooks(*, dry_run: bool = False) -> list[str]:
    """Remove Pathly hook entries from ~/.claude/settings.json.

    Returns list of paths affected.
    """
    settings_file = Path.home() / ".claude" / "settings.json"
    if not settings_file.exists():
        return []

    if dry_run:
        return [str(settings_file)]

    try:
        existing = json.loads(settings_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    hooks: dict = existing.get("hooks", {})

    # Remove old-style named entries.
    hooks.pop("classify_feedback", None)
    hooks.pop("inject_feedback_ttl", None)

    # Remove Pathly entry from PostToolUse list.
    if "PostToolUse" in hooks:
        hooks["PostToolUse"] = [e for e in hooks["PostToolUse"] if not e.get("_pathly")]
        if not hooks["PostToolUse"]:
            hooks.pop("PostToolUse")

    if not hooks:
        existing.pop("hooks", None)

    settings_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return [str(settings_file)]


def _load_manifest(dest: Path) -> dict:
    manifest_path = dest / MANIFEST_NAME
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "_manifest_version" not in data:
                raise ValueError("Manifest missing _manifest_version field")
            files = data.get("files", {})
            if data.get("_manifest_hash", "") != _hash_files_dict(files):
                raise ValueError("Manifest hash mismatch — file may be corrupted or tampered")
            return data
        except (json.JSONDecodeError, OSError):
            return {"files": {}}
    return {"files": {}}


def _save_manifest(dest: Path, manifest: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    manifest["_manifest_version"] = "1"
    manifest["_manifest_hash"] = _hash_files_dict(manifest["files"])
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
    """Copy *.flow.yaml files from the installed package to dest. Returns list of filenames written.

    Flow YAMLs are always authoritative — repair=True is forced so that
    re-running the installer keeps installed flows in sync with the source
    without requiring an explicit --repair flag.
    """
    from .resources import core_flows_path

    flows_src = core_flows_path()
    files: dict[str, str] = {
        f.name: f.read_text(encoding="utf-8")
        for f in sorted(flows_src.glob("*.flow.yaml"))
    }
    return materialize(files, dest, repair=True, force=force, dry_run=dry_run)


def uninstall(dest: Path, *, dry_run: bool = False, confirm_manifest: bool = False) -> list[str]:
    """Remove all Pathly-owned files from dest using the manifest.

    Returns list of filenames removed (or would-remove in dry_run).
    If manifest entries are missing from disk and confirm_manifest is False,
    prints a warning to stderr and aborts without deleting anything.
    If confirm_manifest is True, missing entries are skipped and deletion proceeds.
    """
    manifest_path = dest / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"  [warn] No manifest at {manifest_path} — nothing to uninstall.", file=sys.stderr)
        return []

    manifest = _load_manifest(dest)
    removed: list[str] = []
    missing: list[str] = []

    # Pass 1: validate all entries before touching the filesystem.
    # This prevents partial deletion when a manifest is tampered.
    for name in list(manifest["files"]):
        target = dest / name
        if not target.resolve().is_relative_to(dest.resolve()):
            raise ValueError(
                f"Path traversal detected in manifest: {name!r} escapes destination {dest}"
            )
        if not target.exists():
            missing.append(name)

    if missing and not confirm_manifest:
        print(
            f"  [warn] Aborting uninstall — the following manifest entries are not found on disk:\n"
            + "\n".join(f"    {name}" for name in missing),
            file=sys.stderr,
        )
        return []

    # Pass 2: all entries are clean — perform deletions.
    missing_set = set(missing)
    for name in list(manifest["files"]):
        if name in missing_set:
            continue
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
