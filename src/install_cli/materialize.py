import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = ".pathly-manifest.json"


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
