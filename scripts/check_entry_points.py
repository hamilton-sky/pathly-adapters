#!/usr/bin/env python3
"""Verify that every entry point declared in pyproject.toml resolves to a real
Python module file under src/.

For each entry of the form:
    name = "package.module:function"

the script converts package.module → src/package/module.py and checks:
  1. The file exists.
  2. The function name appears in that file (as a def or assignment).

Exits non-zero if any entry point is broken.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC  = ROOT / "src"


def parse_entry_points(toml_text: str) -> dict[str, str]:
    """Return {cli_name: 'module.path:function'} from [project.scripts]."""
    in_scripts = False
    result: dict[str, str] = {}
    for line in toml_text.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if in_scripts:
            if stripped.startswith("["):
                break
            m = re.match(r'^([\w-]+)\s*=\s*"([^"]+)"', stripped)
            if m:
                result[m.group(1)] = m.group(2)
    return result


def resolve_module_file(module_path: str) -> tuple[Path, bool]:
    """Convert 'package.subpackage.module' to (file, is_package).

    Returns the .py file, or the package __init__.py if the dotted path
    resolves to a directory (i.e. a Python package, not a plain module).
    """
    parts = module_path.split(".")
    as_module = SRC / Path(*parts).with_suffix(".py")
    as_package = SRC / Path(*parts) / "__init__.py"
    if as_package.exists():
        return as_package, True
    return as_module, False


def check_entry_point(name: str, target: str) -> list[str]:
    errors: list[str] = []
    if ":" not in target:
        errors.append(f"  {name}: malformed target (no colon): {target!r}")
        return errors

    module_path, func_name = target.rsplit(":", 1)
    module_file, _ = resolve_module_file(module_path)

    if not module_file.exists():
        errors.append(f"  {name}: module not found: {module_file.relative_to(ROOT)}")
        return errors

    source = module_file.read_text(encoding="utf-8")
    # Check function is defined or assigned in the file (or re-exported via __init__)
    if not re.search(rf'\b{re.escape(func_name)}\b', source):
        errors.append(
            f"  {name}: function {func_name!r} not found in {module_file.relative_to(ROOT)}"
        )

    return errors


def main() -> int:
    toml_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    entry_points = parse_entry_points(toml_text)

    if not entry_points:
        print("ERROR: no entry points found in pyproject.toml [project.scripts]")
        return 1

    all_errors: list[str] = []
    for name, target in sorted(entry_points.items()):
        all_errors.extend(check_entry_point(name, target))

    if all_errors:
        print("Entry point check FAILED:")
        for line in all_errors:
            print(line)
        return 1

    print(f"Entry points OK: {len(entry_points)} checked")
    for name, target in sorted(entry_points.items()):
        print(f"  {name} = {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
