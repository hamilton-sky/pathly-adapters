import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

MANIFEST_NAME = ".pathly-manifest.json"


def _hash_files_dict(files: dict) -> str:
    return hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load_manifest(dest: Path) -> dict:
    manifest_path = dest / MANIFEST_NAME
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "_manifest_version" not in data:
                # Legacy manifest from an older install — treat as fresh.
                return {"files": {}}
            files = data.get("files", {})
            try:
                if data.get("_manifest_hash", "") != _hash_files_dict(files):
                    raise ValueError(
                        "Manifest hash mismatch — file may be corrupted or tampered"
                    )
            except ValueError as e:
                raise RuntimeError(
                    f"Manifest integrity check failed for {dest}: {e} — use --force to bypass"
                ) from e
            return data
        except (json.JSONDecodeError, OSError):
            return {"files": {}}
    return {"files": {}}


def _save_manifest(dest: Path, manifest: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    manifest["_manifest_version"] = "1"
    manifest["_manifest_hash"] = _hash_files_dict(manifest["files"])
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _remove_empty_parents(parent: Path, dest: Path) -> None:
    while parent != dest:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def materialize(
    files: dict[str, str],
    dest: Path,
    *,
    repair: bool = False,
    force: bool = False,
    dry_run: bool = False,
    prune_filter: Callable[[str], bool] | None = None,
) -> list[str]:
    """Synchronize stitched files to dest. Returns filenames written (or would-write)."""
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

    pruned = False
    if repair and not dry_run:
        stale_names = owned - set(files)
        if prune_filter is not None:
            stale_names = {name for name in stale_names if prune_filter(name)}
        for name in sorted(stale_names):
            target = dest / name
            if not target.resolve().is_relative_to(dest.resolve()):
                raise ValueError(
                    f"Path traversal detected in manifest: {name!r} escapes destination {dest}"
                )
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            _remove_empty_parents(target.parent, dest)
            del manifest["files"][name]
            pruned = True

    if not dry_run and (written or pruned):
        _save_manifest(dest, manifest)

    return written


def materialize_flows(
    dest: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Copy *.flow.yaml files from the installed package to dest. Returns list of filenames written.

    Flow YAMLs are always authoritative: repair is forced True so re-running
    the installer keeps installed flows in sync with the source package.
    """
    from .resources import core_flows_path

    flows_src = core_flows_path()
    files: dict[str, str] = {
        f.name: f.read_text(encoding="utf-8")
        for f in sorted(flows_src.glob("*.flow.yaml"))
    }
    return materialize(
        files,
        dest,
        repair=True,
        force=force,
        dry_run=dry_run,
        prune_filter=lambda name: name.endswith(".flow.yaml"),
    )


def uninstall(
    dest: Path, *, dry_run: bool = False, confirm_manifest: bool = False
) -> list[str]:
    """Remove all Pathly-owned files from dest using the manifest.

    Returns list of filenames removed (or would-remove in dry_run).
    If manifest entries are missing from disk and confirm_manifest is False,
    prints a warning to stderr and aborts without deleting anything.
    If confirm_manifest is True, missing entries are skipped and deletion proceeds.
    """
    manifest_path = dest / MANIFEST_NAME
    if not manifest_path.exists():
        print(
            f"  [warn] No manifest at {manifest_path} — nothing to uninstall.",
            file=sys.stderr,
        )
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
            _remove_empty_parents(target.parent, dest)

    if not dry_run:
        try:
            manifest_path.unlink()
        except FileNotFoundError:
            pass

    return removed
